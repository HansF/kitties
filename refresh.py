"""Full refresh of all animals + shelters on adopteereendier.be into data/.

Writes:
  data/animals.json|csv    every listed animal (all categories), newest first
  data/per-soort/<category>.json|csv   the same, split per category
  data/shelters.json|csv   every shelter with contact info and counts
  data/new.json            animals that appeared since the previous refresh
  data/changes.csv         running log of added/removed animals (timestamped)
  data/meta.json           index for apps: last update time, counts, file list

Refuses to overwrite data if a scrape returns far fewer animals than before
(e.g. the site layout changed), so a broken run can't wipe the dataset.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from check_cats import fetch_page
import scrape_shelters

CATEGORIES = ["katten", "honden", "weidedieren", "konijnen-en-knaagdieren", "overigedieren"]
DATA = Path(__file__).parent / "data"
MIN_RATIO = 0.5  # abort if a category shrinks below half its previous size
BASE_URL = "https://hansf.github.io/kitties/data"
LOG_FIELDS = ["time", "change", "category", "id", "type", "name", "shelter", "url"]


def scrape_category(category):
    animals, seen, n = [], set(), 1
    while True:
        page = [a for a in fetch_page(category, n) if a["id"] not in seen]
        if not page:
            return animals
        seen.update(a["id"] for a in page)
        animals.extend({"category": category, **a} for a in page)
        n += 1


def snapshot():
    """Contents of all data files except meta.json, to detect real changes."""
    return {p: p.read_bytes() for p in DATA.rglob("*") if p.is_file() and p.name != "meta.json"}


def write_meta(animals, shelters, added, removed, now, changed):
    meta_file = DATA / "meta.json"
    old = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    files = {"animals": "animals.json", "shelters": "shelters.json", "new": "new.json"}
    files.update({c: f"per-soort/{c}.json" for c in CATEGORIES})
    meta = {
        "updated_at": now if changed or "updated_at" not in old else old["updated_at"],
        "source": "https://www.adopteereendier.be",
        "counts": {
            "total": len(animals),
            **{c: sum(a["category"] == c for a in animals) for c in CATEGORIES},
            "shelters": len(shelters),
        },
        "last_change": {"added": len(added), "removed": len(removed)} if changed else old.get("last_change"),
        "files": {k: f"{BASE_URL}/{v}" for k, v in files.items()},
        "csv": {k: f"{BASE_URL}/{v[:-5]}.csv" for k, v in files.items() if k != "new"},
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def write(name, rows):
    (DATA / name).parent.mkdir(parents=True, exist_ok=True)
    (DATA / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    if rows:
        with open(DATA / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
            w.writeheader()
            w.writerows(rows)


def main():
    DATA.mkdir(exist_ok=True)
    old_file = DATA / "animals.json"
    old = json.loads(old_file.read_text(encoding="utf-8")) if old_file.exists() else []
    old_by_id = {a["id"]: a for a in old}

    animals = []
    for cat in CATEGORIES:
        rows = scrape_category(cat)
        before = sum(a["category"] == cat for a in old)
        print(f"{cat}: {len(rows)} (was {before})")
        if before and len(rows) < before * MIN_RATIO:
            sys.exit(f"ABORT: {cat} dropped from {before} to {len(rows)} - site changed?")
        animals.extend(rows)
    animals.sort(key=lambda a: -a["id"])

    shelters = scrape_shelters.scrape()
    print(f"shelters: {len(shelters)}")
    if len(shelters) < 50:
        sys.exit(f"ABORT: only {len(shelters)} shelters scraped - site changed?")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    new_by_id = {a["id"]: a for a in animals}
    added = [a for a in animals if a["id"] not in old_by_id] if old else []
    removed = [a for i, a in old_by_id.items() if i not in new_by_id]
    print(f"added: {len(added)}, removed: {len(removed)}")

    before = snapshot()
    write("animals", animals)
    for cat in CATEGORIES:
        write(f"per-soort/{cat}", [a for a in animals if a["category"] == cat])
    write("shelters", shelters)
    # empty on the first run: nothing to compare against
    (DATA / "new.json").write_text(json.dumps(added, ensure_ascii=False, indent=1), encoding="utf-8")
    log = DATA / "changes.csv"
    is_new_log = not log.exists()
    with open(log, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS, delimiter=";", extrasaction="ignore")
        if is_new_log:
            w.writeheader()
        for change, rows in (("added", added), ("removed", removed)):
            for a in rows:
                w.writerow({"time": now, "change": change, **a})
    write_meta(animals, shelters, added, removed, now, snapshot() != before)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
