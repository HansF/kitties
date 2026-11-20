"""Scrape each animal's detail page into data/details/<id>.json.

The list pages only carry a teaser. The detail page adds the full description, the shelter's
reference number, every photo and (for dogs and cats) a list of traits such as "Kan met
kinderen om < 6 jaar?" -> "Ja".

Incremental: an animal's page is fetched once; files of animals that are no longer listed are
deleted. A failed fetch is retried on the next run.

Each file:
  {"id", "url", "reference", "sex", "age", "breed", "description", "photos": [...],
   "traits": {"Kan met kinderen om < 6 jaar?": "Ja", ...}, "fetched_at"}

Usage:
  python details.py        fetch details for every animal in data/animals.json that has none yet
"""
import html
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).parent / "data" / "details"
HEADERS = {"User-Agent": "Mozilla/5.0 (kitties hourly snapshot)"}
WORKERS = 4
INFO_FIELDS = {"Geslacht": "sex", "Leeftijd": "age", "Ras": "breed", "Referentie": "reference"}


def _text(fragment):
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", html.unescape(line)).strip() for line in fragment.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def parse(page):
    """Detail fields from a detail page's HTML, or None if it doesn't look like one."""
    out = {}
    for label, value in re.findall(
            r'<div class="grid grid-cols-2 gap-4">\s*<div>\s*([^<:]+?):\s*</div>\s*<div>(.*?)</div>', page, re.S):
        if label.strip() in INFO_FIELDS:
            out[INFO_FIELDS[label.strip()]] = _text(value)
    desc = re.search(r'<p class="my-6 textContent">(.*?)</p>', page, re.S)
    out["description"] = _text(desc.group(1)) if desc else ""
    out["photos"] = list(dict.fromkeys(re.findall(r'<a href="([^"]+)" class="venobox"', page)))
    traits = {}
    start = page.find(">Eigenschappen<")
    if start != -1:
        block = page[start:page.find("</ul>", start)]
        for k, v in re.findall(r'<div class="col-span-3">(.*?)</div>\s*<div class="text-right">(.*?)</div>', block, re.S):
            traits[_text(k)] = _text(v)
    out["traits"] = traits
    if not (out["description"] or out["photos"] or out.get("reference")):
        return None
    return out


def fetch(animal):
    req = urllib.request.Request(animal["url"], headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return parse(r.read().decode("utf-8", "replace"))


def update(animals, limit=None):
    """Fetch details for animals without a file, delete files of delisted animals.

    Never raises on network/parse errors; returns (fetched, failed, removed).
    """
    DIR.mkdir(parents=True, exist_ok=True)
    listed = {a["id"] for a in animals}
    removed = 0
    for f in DIR.glob("*.json"):
        if f.stem.isdigit() and int(f.stem) not in listed:
            f.unlink()
            removed += 1
    todo = [a for a in animals if not (DIR / f"{a['id']}.json").exists()][:limit]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    def one(a):
        try:
            d = fetch(a)
        except Exception as e:  # noqa: BLE001 - retried next run
            return f"{a['id']}: {e}"
        if d is None:
            return f"{a['id']}: no detail fields found"
        d = {"id": a["id"], "url": a["url"], **d, "fetched_at": now}
        (DIR / f"{a['id']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        return None

    with ThreadPoolExecutor(WORKERS) as pool:
        errors = [e for e in pool.map(one, todo) if e]
    for e in errors[:10]:
        print("details failed:", e)
    print(f"details: {len(todo) - len(errors)} fetched, {len(errors)} failed, {removed} removed")
    return len(todo) - len(errors), len(errors), removed


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    animals = json.loads((Path(__file__).parent / "data" / "animals.json").read_text(encoding="utf-8"))
    update(animals, limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
