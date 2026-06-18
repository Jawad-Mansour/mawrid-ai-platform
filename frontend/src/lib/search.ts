// Feature: Catalog — smart product search
// Layer:   Lib / utility
// Purpose: Tokenized, synonym-aware product search. Builds a full searchable corpus
//          from EVERY field (name, sku, barcode, full description, all spec keys AND
//          values, supplier names, source titles) so a term like "silver" also matches
//          products described as "inox / stainless / anthracite". Domain-agnostic —
//          works for appliances, fashion, food, hardware, anything.
import type { Product } from "@/lib/types";

// Bidirectional synonym groups. A query term that lands in a group matches any member.
// Kept general on purpose: colours, finishes, materials, sizes, common categories.
const SYNONYM_GROUPS: string[][] = [
  ["silver", "inox", "stainless", "steel", "grey", "gray", "metallic", "chrome", "platinum", "titanium", "graphite", "anthracite", "argent"],
  ["black", "noir", "onyx", "graphite", "anthracite", "dark"],
  ["white", "blanc", "ivory", "snow", "pearl"],
  ["gold", "golden", "champagne", "brass"],
  ["blue", "navy", "azure", "bleu"],
  ["red", "rouge", "crimson", "burgundy"],
  ["green", "vert", "olive", "emerald"],
  ["beige", "cream", "sand", "taupe"],
  ["small", "compact", "mini"],
  ["large", "big", "jumbo"],
  ["fridge", "refrigerator", "frigo"],
  ["washer", "washing", "laundry"],
  ["dryer", "drying"],
  ["tv", "television"],
  ["phone", "smartphone", "mobile"],
  ["laptop", "notebook", "portable"],
  ["headphone", "headphones", "headset", "earphone", "earbuds"],
  ["wireless", "bluetooth", "cordless"],
];

// Strip accents (combining marks U+0300–U+036F) without an inline regex literal,
// so "televiseur" matches "téléviseur" and "argente" matches "argenté".
function normalize(s: string): string {
  let out = "";
  for (const ch of s.normalize("NFD")) {
    const code = ch.codePointAt(0) ?? 0;
    if (code >= 0x0300 && code <= 0x036f) continue;
    out += ch;
  }
  return out.toLowerCase();
}

function expandTerm(term: string): string[] {
  const t = normalize(term);
  const out = new Set<string>([t]);
  for (const group of SYNONYM_GROUPS) {
    const ng = group.map(normalize);
    if (ng.includes(t)) ng.forEach((g) => out.add(g));
  }
  return [...out];
}

// Everything about a product, flattened to one lowercase, accent-free string.
export function productCorpus(p: Product): string {
  const parts: string[] = [p.product_name, p.sku ?? "", p.barcode ?? "", p.description ?? ""];
  const specs = p.specifications ?? {};
  for (const [k, v] of Object.entries(specs)) {
    parts.push(k, String(v));
  }
  (p.supplier_names ?? []).forEach((s) => parts.push(s));
  (p.source_urls ?? []).forEach((s) => parts.push(s.title ?? "", s.url ?? ""));
  return normalize(parts.join(" | ")).replace(/\s+/g, " ");
}

// Split the corpus into distinct words (letters/digits), for whole-word matching.
function corpusWords(p: Product): Set<string> {
  return new Set(productCorpus(p).split(/[^a-z0-9]+/).filter(Boolean));
}

// One term matches if any of its synonyms is a WHOLE word, a word PREFIX (>=3 chars),
// or — only for longer terms (>=4) — a substring of a word (catches embedded codes
// like "14105" inside "bwm14105ph7"). Whole-word matching kills false positives such
// as "ir" matching "air".
function termMatches(term: string, words: Set<string>): boolean {
  const syns = expandTerm(term);
  for (const s of syns) {
    if (words.has(s)) return true;
    if (s.length >= 3) {
      for (const w of words) {
        if (w.startsWith(s)) return true;
        if (s.length >= 4 && w.includes(s)) return true;
      }
    }
  }
  return false;
}

// AND across query terms; each term may match via any of its synonyms.
export function matchesQuery(p: Product, query: string): boolean {
  const q = query.trim();
  if (!q) return true;
  const words = corpusWords(p);
  const terms = q.split(/\s+/).map(normalize).filter(Boolean);
  return terms.every((term) => termMatches(term, words));
}

// The concrete words to visually highlight for a query (term + its synonyms).
export function highlightTerms(query: string): string[] {
  const q = query.trim();
  if (!q) return [];
  const out = new Set<string>();
  q.split(/\s+/)
    .filter((t) => t.length > 1)
    .forEach((t) => expandTerm(t).forEach((s) => s.length > 1 && out.add(s)));
  return [...out];
}
