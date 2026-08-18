"""
Paso 4 del pipeline: publicación.

Lee data/news.json (ya filtrado, deduplicado y con resumen extraído)
y genera output/index.html usando templates/index.html.j2.
"""

import json
from datetime import datetime, timezone

import yaml
from jinja2 import Environment, FileSystemLoader

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def format_date(iso_date):
    if not iso_date:
        return "fecha s/d"
    y, m, d = iso_date.split("-")
    return f"{int(d)} {MESES[int(m) - 1]} {y}"


def main(news_path="data/news.json", config_path="config/sources.yaml", output_path="output/index.html"):
    with open(news_path, "r", encoding="utf-8") as f:
        news = json.load(f)

    with open(config_path, "r", encoding="utf-8") as f:
        sources_count = len(yaml.safe_load(f)["sources"])

    # más nuevas primero
    news = sorted(news, key=lambda n: n.get("published") or "", reverse=True)
    for n in news:
        n["published_display"] = format_date(n.get("published"))

    categories = sorted({n["category"] for n in news})
    sources_list = sorted({n["source"] for n in news})
    scopes = sorted({n.get("scope", "nacional") for n in news})

    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index.html.j2")

    html = template.render(
        news=news,
        categories=categories,
        sources_list=sources_list,
        scopes=scopes,
        sources_count=sources_count,
        generated_at=datetime.now(timezone.utc).strftime("%d/%m/%Y · %H:%M UTC"),
        next_run="según cron configurado",
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generado -> {output_path} ({len(news)} noticias)")


if __name__ == "__main__":
    main()
