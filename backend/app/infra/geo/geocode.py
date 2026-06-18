"""
Feature:  Supplier & Factory Network — geocoding
Layer:    Infra / Geo
Module:   app.infra.geo.geocode
Purpose:  Turn a free-text location ("Brugherio, Italy") into real lat/lon using
          OpenStreetMap Nominatim (free, no key). Respectful: bounded timeout,
          a descriptive User-Agent, and an in-process cache. Returns None on
          failure — callers must NOT fabricate coordinates (no map pin is better
          than a wrong one).
Depends:  httpx
HITL:     None.
"""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_cache: dict[str, tuple[float, float] | None] = {}
_detail_cache: dict[str, dict[str, object] | None] = {}


async def geocode(location: str | None) -> tuple[float, float] | None:
    """Return (lat, lon) for a place string, or None. Cached per process."""
    if not location or not location.strip():
        return None
    key = location.strip().lower()
    if key in _cache:
        return _cache[key]
    try:
        async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "MawridPlatform/1.0 (supplier-map)"}) as client:
            r = await client.get(
                _NOMINATIM,
                params={"q": location.strip(), "format": "json", "limit": "1"},
            )
            r.raise_for_status()
            data = r.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                _cache[key] = (lat, lon)
                return _cache[key]
    except Exception as exc:  # noqa: BLE001
        logger.warning("geocode_failed", location=location, error=str(exc))
    _cache[key] = None
    return None


# country-code (ISO-3166 alpha-2) → international dialing prefix (the ones we care about)
_DIAL_CODES: dict[str, str] = {
    "it": "+39", "de": "+49", "fr": "+33", "es": "+34", "gb": "+44", "uk": "+44",
    "nl": "+31", "se": "+46", "ch": "+41", "si": "+386", "pl": "+48", "dk": "+45",
    "be": "+32", "at": "+43", "pt": "+351", "ie": "+353", "fi": "+358", "no": "+47",
    "cz": "+420", "tr": "+90", "lb": "+961", "ae": "+971", "sa": "+966", "us": "+1",
    "cn": "+86", "au": "+61", "gr": "+30", "ro": "+40", "hu": "+36",
}


async def geocode_detailed(query: str | None) -> dict[str, object] | None:
    """Resolve a place to real address details: lat/lon, city, country, country_code,
    dial-code and a display name. Returns None on failure (never fabricate)."""
    if not query or not query.strip():
        return None
    key = query.strip().lower()
    if key in _detail_cache:
        return _detail_cache[key]
    try:
        async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "MawridPlatform/1.0 (supplier-map)"}) as client:
            r = await client.get(
                _NOMINATIM,
                params={"q": query.strip(), "format": "json", "limit": "1", "addressdetails": "1"},
            )
            r.raise_for_status()
            data = r.json()
            if data:
                d = data[0]
                addr = d.get("address", {}) or {}
                cc = str(addr.get("country_code", "")).lower()
                city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("state")
                out: dict[str, object] = {
                    "latitude": float(d["lat"]),
                    "longitude": float(d["lon"]),
                    "city": city,
                    "country": addr.get("country"),
                    "country_code": cc,
                    "phone_code": _DIAL_CODES.get(cc, ""),
                    "display_name": d.get("display_name"),
                }
                _detail_cache[key] = out
                return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("geocode_detailed_failed", query=query, error=str(exc))
    _detail_cache[key] = None
    return None
