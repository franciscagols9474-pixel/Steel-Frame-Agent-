"""
Pasos 2 y 3 del pipeline: filtrado de relevancia y deduplicación.

Filtro: un item pasa si el título o el resumen crudo contienen alguna
de las keywords configuradas (case-insensitive).

Deduplicación combinada:
  a) URL normalizada exacta (mismo artículo, distinto parámetro de tracking)
  b) Similitud de título (>= TITLE_SIMILARITY_THRESHOLD) entre notas de
     DISTINTAS fuentes -> típico caso de nota de agencia republicada.
     Ante un duplicado, se conserva el item con fecha más reciente.

Resumen: extracción simple (sin IA). Se usa meta og:description /
meta description de la página, con fallback al primer párrafo del
raw_summary del feed, recortado a ~220 caracteres.
"""

import difflib
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

TITLE_SIMILARITY_THRESHOLD = 0.82
SUMMARY_MAX_CHARS = 220
REQUEST_TIMEOUT = 8
USER_AGENT = "Mozilla/5.0 (compatible; SteelFrameARBot/1.0; +https://example.org/bot)"


def is_relevant(item, keywords):
    haystack = f"{item['title']} {item['raw_summary']}".lower()
    return any(kw.lower() in haystack for kw in keywords)


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    # saca parámetros de tracking (utm_*, gclid, fbclid, etc.)
    query = urllib.parse.parse_qsl(parsed.query)
    clean_query = [(k, v) for k, v in query if not k.lower().startswith(("utm_", "gclid", "fbclid"))]
    clean = parsed._replace(query=urllib.parse.urlencode(clean_query), fragment="")
    return urllib.parse.urlunparse(clean).rstrip("/")


def _clean_html(raw_html: str) -> str:
    return re.sub(r"<[^>]+>", " ", raw_html or "").strip()


def extract_summary_and_image(url: str, fallback_text: str):
    """Extracción simple: lee meta og:description / og:image de la página."""
    summary = _clean_html(fallback_text)[:SUMMARY_MAX_CHARS]
    image = None
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(resp.text, "html.parser")

        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            summary = og_desc["content"].strip()[:SUMMARY_MAX_CHARS]

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image = og_image["content"].strip()
    except Exception as exc:
        print(f"[extract] no se pudo leer {url}: {exc}")

    if summary and not summary.endswith((".", "…")):
        summary = summary.rstrip(", ") + "…"
    return summary, image


def dedupe(items):
    seen_urls = {}
    deduped = []

    for item in items:
        key = normalize_url(item["url"])
        if key in seen_urls:
            continue
        seen_urls[key] = True

        is_duplicate = False
        for existing in deduped:
            similarity = difflib.SequenceMatcher(None, item["title"].lower(), existing["title"].lower()).ratio()
            if similarity >= TITLE_SIMILARITY_THRESHOLD:
                is_duplicate = True
                # se queda con el más reciente
                if (item.get("published") or "") > (existing.get("published") or ""):
                    deduped.remove(existing)
                    deduped.append(item)
                break
        if not is_duplicate:
            deduped.append(item)

    return deduped


def process(raw_items, keywords):
    relevant = [item for item in raw_items if is_relevant(item, keywords)]
    print(f"[filter] {len(relevant)}/{len(raw_items)} items relevantes")

    deduped = dedupe(relevant)
    print(f"[dedupe] {len(deduped)}/{len(relevant)} items tras deduplicar")

    enriched = []
    for item in deduped:
        summary, image = extract_summary_and_image(item["url"], item["raw_summary"])
        enriched.append({
            **item,
            "summary": summary,
            "image": image,
        })
    return enriched


if __name__ == "__main__":
    import json
    from fetch_sources import load_sources

    _sources, keywords = load_sources()
    with open("data/raw_items.json", "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    processed = process(raw_items, keywords)
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)
    print(f"Guardado -> data/news.json ({len(processed)} noticias)")
