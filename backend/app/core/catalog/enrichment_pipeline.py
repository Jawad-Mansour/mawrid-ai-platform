"""
Feature:  Catalog Enrichment Pipeline (Sequential)
Layer:    Core / Service
Module:   app.core.catalog.enrichment_pipeline
Purpose:  Phase 2.4 — Deterministic 5-step enrichment pipeline per extracted product.
          Step 1: Icecat Open lookup (EAN → name fallback).
          Step 2: SearXNG meta-search for web specs.
          Step 3: httpx + trafilatura — fetch and clean top 3 pages.
          Step 4: GPT-4o spec extraction from web content.
          Step 5: GPT-4o description generation.
          Confidence: high (Icecat EAN + spec_count ≥ 5), medium (name + spec_count ≥ 3),
          partial (SearXNG only or no specs found).
          This is NOT a LangGraph agent — Phase 8's Enrichment Specialist wraps
          this pipeline in a single LangGraph node.
Depends:  app.infra.llm.openai, httpx, trafilatura
HITL:     None — enrichment is internal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import structlog
import trafilatura

from app.infra.llm.openai import chat_completion

logger = structlog.get_logger(__name__)

_ICECAT_BASE = "https://icecat.us/api"
_SEARXNG_TIMEOUT = 8.0
_HTTPX_TIMEOUT = 10.0
_MAX_WEB_CHARS = 14000  # truncate scraped content to stay within GPT-4o context
_TOP_URLS = 5


# ── Protocols for dependency injection (testable without network) ─────────────


class _IcecatClient(Protocol):
    async def lookup_ean(self, ean: str) -> dict[str, object] | None: ...

    async def lookup_name(self, name: str) -> dict[str, object] | None: ...


class _SearxngClient(Protocol):
    async def search(self, query: str) -> list[str]: ...

    async def search_images(self, query: str) -> list[dict[str, str]]: ...


class _WebFetcher(Protocol):
    async def fetch_and_clean(self, url: str) -> str: ...


# ── Data types ────────────────────────────────────────────────────────────────


@dataclass
class EnrichmentInput:
    product_name: str
    sku: str | None = None
    barcode: str | None = None
    price: float | None = None
    currency: str | None = None
    specifications: dict[str, str] = field(default_factory=dict)


@dataclass
class EnrichmentOutput:
    product_name: str
    sku: str | None
    barcode: str | None
    price: float | None
    currency: str | None
    specifications: dict[str, str]
    description: str
    image_url: str | None
    enrichment_source: str
    enrichment_confidence: str
    source_urls: list[dict[str, str]] = field(default_factory=list)


# ── Real network clients ──────────────────────────────────────────────────────


class IcecatClient:
    """Icecat Open REST API client. Auth = Basic(username, empty-password)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def lookup_ean(self, ean: str) -> dict[str, object] | None:
        try:
            async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
                resp = await client.get(
                    f"{_ICECAT_BASE}/products",
                    params={"ean": ean, "language": "en"},
                    auth=(self._api_key, ""),
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    return None
                data: dict[str, object] = resp.json()
                return data.get("data") or None  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("icecat_ean_lookup_failed", ean=ean, error=str(exc))
            return None

    async def lookup_name(self, name: str) -> dict[str, object] | None:
        try:
            async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
                resp = await client.get(
                    f"{_ICECAT_BASE}/products",
                    params={"query": name, "language": "en"},
                    auth=(self._api_key, ""),
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    return None
                data: dict[str, object] = resp.json()
                results = data.get("data")
                if isinstance(results, list) and results:
                    item = results[0]
                    return item if isinstance(item, dict) else None
                return None
        except Exception as exc:
            logger.warning("icecat_name_lookup_failed", name=name, error=str(exc))
            return None


class SearxngClient:
    """SearXNG meta-search client. Returns list of result URLs."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=_SEARXNG_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={"q": query, "format": "json", "categories": "general"},
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    return []
                payload: dict[str, object] = resp.json()
                results = payload.get("results", [])
                if not isinstance(results, list):
                    return []
                return [str(r["url"]) for r in results if isinstance(r, dict) and r.get("url")][
                    :_TOP_URLS
                ]
        except Exception as exc:
            logger.warning("searxng_search_failed", query=query, error=str(exc))
            return []

    async def search_images(self, query: str) -> list[dict[str, str]]:
        """Return image results (img_src, title, resolution, source) for picking the
        real product photo — far more reliable than scraping the first og:image."""
        try:
            async with httpx.AsyncClient(timeout=_SEARXNG_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={"q": query, "format": "json", "categories": "images"},
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    return []
                results = resp.json().get("results", [])
                out: list[dict[str, str]] = []
                if isinstance(results, list):
                    for r in results:
                        if isinstance(r, dict) and r.get("img_src"):
                            out.append(
                                {
                                    "img_src": str(r.get("img_src", "")),
                                    "title": str(r.get("title", "")),
                                    "resolution": str(r.get("resolution", "")),
                                    "source": str(r.get("source", "")),
                                    "url": str(r.get("url", "")),
                                }
                            )
                return out
        except Exception as exc:
            logger.warning("searxng_image_search_failed", query=query, error=str(exc))
            return []


# Image hosts/terms that are never a real product photo, and spare-part terms.
_IMG_REJECT = (
    ".svg", "devicon", "lucide", "jsdelivr", "placeholder", "sprite", "/logo", "icon-",
    "pexels.com", "unsplash.com", "artic.edu", "pagesjaunes", "gravatar", "wikimedia/commons/thumb/.*/l-",
)
_PART_TERMS = (
    "motor", "pump", "spare", "replacement part", " seal", "gasket", "hose", "belt",
    "pcb", "circuit board", "drain", "heating element", "exploded", "diagram", "schematic",
    "door handle", "knob", "bearing", " parts ",
)
# Authoritative sources (manufacturers + major retailers) — their product photos are
# far more likely to be the correct item than a random marketplace re-upload.
_GOOD_IMG_DOMAINS = (
    "amazon", "carrefour", "xcite", "choice", "currys", "ao.com", "manua.ls", "icecat",
    "candy", "hoover", "bosch", "lg.com", "samsung", "teka", "whirlpool", "noon",
    "sharafdg", "extra.com", "jarir", "mediamarkt", "darty", "ldlc", "boulanger",
    "manufacturer", "/dam/", "officialsite",
)


def _pick_product_image(
    images: list[dict[str, str]], brand: str, model: str, product_name: str
) -> str | None:
    """Score image-search results and return the best real product photo, or None."""
    import re  # noqa: PLC0415

    name_tokens = {t for t in re.findall(r"[a-z0-9]+", product_name.lower()) if len(t) > 2}
    model_l = re.sub(r"[^a-z0-9]", "", (model or "").lower())
    # When we know the model/SKU code, the photo MUST contain it — otherwise we'd risk
    # attaching a *different* code's product (a frequent enrichment error). Better no image.
    strict = len(model_l) >= 4  # noqa: PLR2004
    brand_l = (brand or "").lower().strip()
    best: str | None = None
    best_score = 0.0

    for im in images[:30]:
        src = im.get("img_src", "")
        low = src.lower()
        title = im.get("title", "").lower()
        if not low.startswith("http"):
            continue
        if any(b in low for b in _IMG_REJECT):
            continue
        if any(p in (title + " " + low) for p in _PART_TERMS):  # reject spare-part photos
            continue

        norm = re.sub(r"[^a-z0-9]", "", low + " " + title)
        model_ok = bool(model_l) and model_l in norm
        if strict and not model_ok:
            continue  # never attach a different model's photo when we know the code

        score = 0.0
        title_tokens = {t for t in re.findall(r"[a-z0-9]+", title) if len(t) > 2}
        score += len(name_tokens & title_tokens)
        if model_ok:
            score += 6
        if brand_l and brand_l in (low + " " + title):
            score += 1.5
        res = im.get("resolution", "")
        nums = re.findall(r"(\d{2,4})", res)
        if len(nums) >= 2:  # noqa: PLR2004
            w = int(nums[0])
            if w >= 400:  # noqa: PLR2004
                score += 1
            if w >= 800:  # noqa: PLR2004
                score += 0.5
        if any(h in low for h in ("/media", "catalog", "/product", "/dam/", "/images")):
            score += 0.5
        # authoritative source boost — trust manufacturer/major-retailer photos
        if any(d in low for d in _GOOD_IMG_DOMAINS):
            score += 2.5

        if score > best_score:
            best_score = score
            best = src

    # Strict candidates already match the model (≥6); otherwise require a meaningful match.
    threshold = 1.0 if strict else 2.0
    return best if best_score >= threshold else None


def _extract_og_image(html: str, base_url: str) -> str | None:
    """Pull the primary product image (og:image / twitter:image) from page HTML."""
    import re  # noqa: PLC0415
    from urllib.parse import urljoin  # noqa: PLC0415

    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            url = m.group(1).strip()
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = urljoin(base_url, url)
            if url.startswith("http"):
                return url
    return None


class WebFetcher:
    """Fetches a URL and returns cleaned plaintext via trafilatura, plus the
    page's primary image (og:image) for the AI-overview style product image."""

    async def fetch_and_clean(self, url: str) -> str:
        text, _ = await self.fetch_page(url)
        return text

    async def fetch_page(self, url: str) -> tuple[str, str | None]:
        """Return (cleaned_text, og_image_url)."""
        try:
            async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code >= 400:  # noqa: PLR2004
                    return "", None
                text = (trafilatura.extract(resp.text) or "")[:_MAX_WEB_CHARS]
                image = _extract_og_image(resp.text, str(resp.url))
                return text, image
        except Exception as exc:
            logger.warning("web_fetch_failed", url=url, error=str(exc))
            return "", None


# ── Icecat response parsing ───────────────────────────────────────────────────


def _parse_icecat(
    data: dict[str, object],
    matched_by: str,
) -> tuple[dict[str, str], str | None, int, str]:
    """
    Extract specs, image URL, spec count, and confidence from Icecat response.
    Returns (specs, image_url, spec_count, source).
    """
    specs: dict[str, str] = {}
    image_url: str | None = None

    features_groups = data.get("FeaturesGroups") or data.get("featuresGroups") or []
    if isinstance(features_groups, list):
        for group in features_groups:
            if not isinstance(group, dict):
                continue
            features = group.get("Features") or group.get("features") or []
            if not isinstance(features, list):
                continue
            for feat in features:
                if not isinstance(feat, dict):
                    continue
                name = feat.get("Feature", {})
                if isinstance(name, dict):
                    key = str(name.get("Name") or name.get("name") or "")
                else:
                    key = str(name)
                value = str(feat.get("Value") or feat.get("value") or "")
                if key and value:
                    specs[key] = value

    img_data = data.get("Image") or data.get("image") or {}
    if isinstance(img_data, dict):
        image_url = str(img_data.get("HighPic") or img_data.get("highPic") or "") or None

    spec_count = len(specs)
    confidence: str
    if matched_by == "ean" and spec_count >= 5:  # noqa: PLR2004
        confidence = "high"
    elif spec_count >= 3:  # noqa: PLR2004
        confidence = "medium"
    else:
        confidence = "partial"

    return specs, image_url, spec_count, confidence


# ── GPT-4o spec fill ─────────────────────────────────────────────────────────

_SPEC_FILL_PROMPT = """\
You are a product research specialist writing a catalogue entry for an importer,
similar to a Google "AI overview" for a product code.

You are given the product name/code, any existing specifications, and web content
scraped from manufacturer pages, manuals, retailers and parts distributors.

Return ONLY valid JSON (no markdown fences) with exactly these keys:
{
  "specifications": { "<Title Case key>": "<value>" },
  "description": "<rich Markdown description, see structure below>"
}

This product can be from ANY category — appliances, electronics, apparel & textiles,
food & grocery, beauty & cosmetics, tools & hardware, furniture, toys, auto parts, etc.
FIRST identify the exact product TYPE and category from the web content, then state the
true type and ALL key figures (don't under-describe: a "washer-dryer combo" is not just a
"washing machine"; state both wash AND dry capacity).

The "description" MUST be detailed Markdown. ALWAYS include the summary, Core
Specifications and Key Features. Then include ONLY the additional sections that fit this
product's category (omit the rest entirely — never force appliance sections onto a t-shirt):

<a precise 1-2 sentence summary naming the exact product type, headline figures, and who it's for>

## Core Specifications
- **<Spec name>:** <value>   (the most important attributes for THIS category — e.g.
  appliance: capacity/power/dimensions; apparel: material/fit/sizes; food: weight/ingredients;
  electronics: chipset/storage/ports; cosmetics: volume/skin-type)

## Key Features
- <notable feature with a short benefit>

Then choose the relevant ones (and only those with real info):
- **## Materials & Care** (apparel, textiles, furniture) — material, wash/care instructions
- **## Sizing & Fit** (apparel, footwear) — size range, fit
- **## Ingredients & Nutrition** (food, grocery) — ingredients, nutrition, weight, allergens
- **## How to Use** (cosmetics, supplements, consumables)
- **## In the Box / Compatibility** (electronics, accessories) — what's included, what it works with
- **## Manuals & Resources** (appliances, electronics, tools) — manuals/official resources
- **## Replacement Parts & Maintenance** (serviceable appliances/devices only)

Rules:
- Ground every claim in the web content or existing specs — do NOT invent numbers.
- NEVER invent URLs. Only use a Markdown link if the exact URL appears in the web content;
  otherwise describe the resource in plain text with no link.
- Avoid vague filler values ("Durable", "Standard", "Compliant with industry standards").
  If you don't have a real value for a spec, omit that spec entirely.
- Be specific (capacities, cycle times, motor type, materials, model compatibilities).
- For the "specifications" object give 6-15 of the most important spec key/value pairs.
- Keep spec keys short and in Title Case (e.g. "Wash Capacity", "Motor Type", "Spin Speed").
- Write in clear English. Return ONLY the JSON object.
"""


async def _gpt4o_enrich(
    product_name: str,
    existing_specs: dict[str, str],
    web_content: str,
) -> tuple[dict[str, str], str]:
    """Returns (merged_specs, description)."""
    user_content = json.dumps(
        {
            "product_name": product_name,
            "existing_specifications": existing_specs,
            "web_content": web_content[:_MAX_WEB_CHARS],
        },
        ensure_ascii=False,
    )
    messages: list[dict[str, object]] = [
        {"role": "system", "content": _SPEC_FILL_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        raw = await chat_completion(messages, temperature=0.0, max_tokens=1800)
        import re  # noqa: PLC0415

        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        parsed: dict[str, object] = json.loads(cleaned)
        merged_specs: dict[str, str] = dict(existing_specs)
        new_specs = parsed.get("specifications", {})
        if isinstance(new_specs, dict):
            merged_specs.update({str(k): str(v) for k, v in new_specs.items()})
        description = str(parsed.get("description") or "")
    except Exception as exc:
        logger.warning("gpt4o_enrich_failed", product=product_name, error=str(exc))
        merged_specs = dict(existing_specs)
        description = ""

    return merged_specs, description


# ── Main pipeline ─────────────────────────────────────────────────────────────


class SequentialEnrichmentPipeline:
    """
    5-step sequential enrichment pipeline. One call per product.
    All network calls gracefully degrade: a timeout or error in any step
    does not abort the pipeline — the product is still enriched with
    whatever data was gathered before the failure.
    """

    def __init__(
        self,
        icecat: _IcecatClient,
        searxng: _SearxngClient,
        fetcher: _WebFetcher,
    ) -> None:
        self._icecat = icecat
        self._searxng = searxng
        self._fetcher = fetcher

    async def run(self, inp: EnrichmentInput) -> EnrichmentOutput:
        specs: dict[str, str] = dict(inp.specifications)
        image_url: str | None = None
        confidence = "partial"
        source = "web"
        source_urls: list[dict[str, str]] = []

        # ── Step 1: Icecat ────────────────────────────────────────────────────
        icecat_data: dict[str, object] | None = None
        matched_by = "name"

        try:
            if inp.barcode:
                icecat_data = await self._icecat.lookup_ean(inp.barcode)
                matched_by = "ean"

            if icecat_data is None:
                icecat_data = await self._icecat.lookup_name(inp.product_name)
                matched_by = "name"
        except Exception as exc:
            logger.warning("icecat_client_error", product=inp.product_name, error=str(exc))

        if icecat_data is not None:
            icecat_specs, image_url, spec_count, confidence = _parse_icecat(icecat_data, matched_by)
            specs.update(icecat_specs)
            source = "icecat"
            source_urls.append({"title": "Icecat product database", "url": "https://icecat.biz"})
            logger.info(
                "icecat_hit",
                product=inp.product_name,
                matched_by=matched_by,
                spec_count=spec_count,
                confidence=confidence,
            )

        # ── Step 2: Image search (once) — pick the correct product photo AND
        #    harvest the retailer/product pages + listing titles it appears on. ────
        image_pages: list[str] = []
        listing_titles: list[str] = []
        _search_images = getattr(self._searxng, "search_images", None)
        if _search_images is not None and (image_url is None or confidence != "high"):
            brand = str(inp.specifications.get("Brand", "")) or (
                inp.product_name.split()[0] if inp.product_name else ""
            )
            try:
                # Anchor the image search on the model/SKU code for precision; fall back to
                # the plain name only if the code-anchored search returns nothing.
                model_code = (inp.sku or "").strip()
                img_query = f"{brand} {model_code} {inp.product_name}".strip() if model_code else inp.product_name
                imgs = await _search_images(img_query)
                if model_code and not imgs:
                    imgs = await _search_images(inp.product_name)
                searched = _pick_product_image(imgs, brand, model_code, inp.product_name)
                if searched:
                    image_url = searched
                image_pages = [
                    str(im.get("url"))
                    for im in imgs[:8]
                    if im.get("url") and str(im.get("url")).startswith("http")
                ]
                listing_titles = [str(im.get("title", "")).strip() for im in imgs[:10] if im.get("title")]
            except Exception as exc:  # noqa: BLE001
                logger.warning("image_search_failed", product=inp.product_name, error=str(exc))

        # ── Step 3: Web research — general search + the product pages from image
        #    search (those carry the true type & capacities). Scrape & clean. ──────
        web_text = ""
        if confidence != "high":
            from urllib.parse import urlparse  # noqa: PLC0415

            q_specs = f"{inp.product_name} {inp.sku or ''} specifications".strip()
            urls_a = await self._searxng.search(q_specs)
            urls_b = await self._searxng.search(inp.product_name)
            ordered = [*image_pages[:3], *urls_a, *urls_b, *image_pages[3:]]
            urls = list(dict.fromkeys(ordered))[:7]  # order-preserving de-dup

            page_texts: list[str] = []
            _fetch_page = getattr(self._fetcher, "fetch_page", None)
            for url in urls:
                if _fetch_page is not None:
                    text, page_image = await _fetch_page(url)
                else:  # fakes that only implement fetch_and_clean
                    text, page_image = await self._fetcher.fetch_and_clean(url), None
                if text:
                    page_texts.append(text)
                    source_urls.append({"title": urlparse(url).netloc or url, "url": url})
                if image_url is None and page_image:
                    image_url = page_image  # final fallback for the photo
            web_text = "\n\n---\n\n".join(page_texts)
            if source != "icecat" and web_text:
                source = "web"

        # de-dup source links by url (order-preserving)
        _seen_src: set[str] = set()
        _deduped: list[dict[str, str]] = []
        for _s in source_urls:
            if _s["url"] not in _seen_src:
                _seen_src.add(_s["url"])
                _deduped.append(_s)
        source_urls = _deduped

        # ── Steps 4 & 5: GPT-4o spec fill + description ───────────────────────
        # Retailer listing titles often name the exact type (e.g. "10/6 kg Washer
        # Dryer") — give them to the model so it doesn't under-describe the product.
        if listing_titles:
            titles_blob = "Retailer/product listing titles (authoritative for the exact product type and capacities):\n" + "\n".join(
                f"- {t}" for t in listing_titles[:10]
            )
            web_text = f"{titles_blob}\n\n{web_text}"
        merged_specs, description = await _gpt4o_enrich(inp.product_name, specs, web_text)

        # If confidence is still partial but we got decent specs now, bump it
        if confidence == "partial" and len(merged_specs) >= 3:  # noqa: PLR2004
            confidence = "medium"

        return EnrichmentOutput(
            product_name=inp.product_name,
            sku=inp.sku,
            barcode=inp.barcode,
            price=inp.price,
            currency=inp.currency,
            specifications=merged_specs,
            description=description,
            image_url=image_url,
            enrichment_source=source,
            enrichment_confidence=confidence,
            source_urls=source_urls,
        )


def build_pipeline(icecat_api_key: str, searxng_base_url: str) -> SequentialEnrichmentPipeline:
    """Factory — constructs the real pipeline with live network clients."""
    return SequentialEnrichmentPipeline(
        icecat=IcecatClient(icecat_api_key),
        searxng=SearxngClient(searxng_base_url),
        fetcher=WebFetcher(),
    )
