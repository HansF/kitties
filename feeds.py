"""RSS 2.0 feeds of the newest animals: data/feeds/all.xml and data/feeds/<category>.xml.

Each feed holds the FEED_SIZE newest animals (highest id first). An item's pubDate is the
time the animal first showed up in data/changes.csv, falling back to when its detail page was
fetched. The output only changes when the listings change, so a quiet refresh commits nothing.

Usage:
  python feeds.py        rebuild the feeds from data/animals.json
"""
import csv
import html
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

DATA = Path(__file__).parent / "data"
SITE = "https://hansf.github.io/kitties"
FEED_SIZE = 50
TITLES = {
    "all": "All animals",
    "katten": "Cats",
    "honden": "Dogs",
    "weidedieren": "Farm animals",
    "konijnen-en-knaagdieren": "Rabbits & rodents",
    "overigedieren": "Birds, reptiles & other animals",
}


def _parse_time(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def first_seen():
    """id -> datetime the animal was first logged as added."""
    seen = {}
    log = DATA / "changes.csv"
    if log.exists():
        with open(log, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter=";"):
                t = _parse_time(row["time"])
                if row["change"] == "added" and t and row["id"].isdigit():
                    seen.setdefault(int(row["id"]), t)
    return seen


def _details(animal_id):
    f = DATA / "details" / f"{animal_id}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _item(a, published):
    d = _details(a["id"])
    facts = " · ".join(x for x in (a.get("type"), a.get("breed") if a.get("breed") != "-" else "",
                                    a.get("sex"), a.get("age")) if x)
    text = d.get("description") or a.get("summary", "")
    body = "".join([
        f'<p><img src="{html.escape(a["image"])}" alt="{html.escape(a["name"])}" style="max-width:100%"></p>'
        if a.get("image") else "",
        f"<p><b>{html.escape(facts)}</b></p>" if facts else "",
        f'<p>{html.escape(a["shelter"])}, {html.escape(a["location"].title())}</p>',
        "".join(f"<p>{html.escape(p)}</p>".replace("\n", "<br>") for p in text.split("\n\n") if p.strip()),
    ])
    title = f'{a["name"]} ({facts})' if facts else a["name"]
    parts = [
        f"<title>{escape(title)}</title>",
        f"<link>{escape(a['url'])}</link>",
        f'<guid isPermaLink="false">adopteereendier-{a["id"]}</guid>',
        f"<pubDate>{format_datetime(published)}</pubDate>" if published else "",
        f"<category>{escape(TITLES[a['category']])}</category>",
        f"<description>{escape(body)}</description>",
        f'<enclosure url="{escape(a["image"])}" length="0" type="image/jpeg"/>' if a.get("image") else "",
    ]
    return "  <item>\n" + "".join(f"   {p}\n" for p in parts if p) + "  </item>\n"


def build(name, animals, seen):
    items, dates = [], []
    for a in animals[:FEED_SIZE]:
        published = seen.get(a["id"]) or _parse_time(_details(a["id"]).get("fetched_at"))
        dates.append(published)
        items.append(_item(a, published))
    newest = max((d for d in dates if d), default=None)
    self_url = f"{SITE}/data/feeds/{name}.xml"
    head = [
        f"<title>Adopt a pet in Flanders: {escape(TITLES[name])}</title>",
        f"<link>{SITE}/map.html</link>",
        f'<atom:link href="{self_url}" rel="self" type="application/rss+xml"/>',
        f"<description>Newest {escape(TITLES[name].lower())} up for adoption on adopteereendier.be</description>",
        "<language>nl-BE</language>",
        f"<lastBuildDate>{format_datetime(newest)}</lastBuildDate>" if newest else "",
        "<ttl>60</ttl>",
    ]
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n <channel>\n'
            + "".join(f"  {h}\n" for h in head if h) + "".join(items) + " </channel>\n</rss>\n")


def write_feeds(animals):
    """Write data/feeds/all.xml and one feed per category. `animals` must be sorted newest first."""
    out = DATA / "feeds"
    out.mkdir(parents=True, exist_ok=True)
    seen = first_seen()
    for name in TITLES:
        rows = animals if name == "all" else [a for a in animals if a["category"] == name]
        (out / f"{name}.xml").write_text(build(name, rows, seen), encoding="utf-8", newline="\n")
    print(f"feeds: {len(TITLES)} written")


if __name__ == "__main__":
    write_feeds(json.loads((DATA / "animals.json").read_text(encoding="utf-8")))
