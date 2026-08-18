"""
Paso 1 del pipeline: recolección.

Lee config/sources.yaml, baja cada fuente (RSS directo o búsqueda en
Google News RSS) y devuelve una lista de items en un esquema común:

    {
        "title": str,
        "url": str,
        "source": str,
        "published": "YYYY-MM-DD" | None,
        "raw_summary": str,   # lo que trae el feed, sin procesar
        "category": str,      # categoría por defecto de la fuente
        "scope": str,         # "nacional" | "regional"
    }

No filtra relevancia ni deduplica todavía — eso lo hace filter_dedupe.py.
"""

import urllib.parse
import feedparser
import yaml


def load_sources(config_path="config/sources.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["sources"], config["keywords"]


def _google_news_rss_url(query: str) -> str:
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=es-419&gl=AR&ceid=AR:es-419"


def fetch_rss(url: str, source_name: str, default_category: str, default_scope: str):
    parsed = feedparser.parse(url)
    items = []
    for entry in parsed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = f"{entry.published_parsed.tm_year:04d}-{entry.published_parsed.tm_mon:02d}-{entry.published_parsed.tm_mday:02d}"
        items.append({
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", "").strip(),
            "source": source_name,
            "published": published,
            "raw_summary": entry.get("summary", "").strip(),
            "category": default_category,
            "scope": default_scope,
        })
    return items


def fetch_all(config_path="config/sources.yaml"):
    sources, _keywords = load_sources(config_path)
    all_items = []
    for src in sources:
        try:
            scope = src.get("default_scope", "nacional")
            if src["type"] == "rss":
                items = fetch_rss(src["url"], src["name"], src.get("default_category", "actualidad"), scope)
            elif src["type"] == "gnews":
                feed_url = _google_news_rss_url(src["query"])
                items = fetch_rss(feed_url, src["name"], src.get("default_category", "actualidad"), scope)
            else:
                continue
            print(f"[fetch] {src['name']}: {len(items)} items")
            all_items.extend(items)
        except Exception as exc:
            # Una fuente caída no debe tirar abajo todo el pipeline.
            print(f"[fetch] ERROR en {src['name']}: {exc}")
    return all_items


if __name__ == "__main__":
    import json
    items = fetch_all()
    with open("data/raw_items.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Total recolectado: {len(items)} items -> data/raw_items.json")
