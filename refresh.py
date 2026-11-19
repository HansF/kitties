"""Full refresh of all animals + shelters on adopteereendier.be into data/.

Writes:
  data/animals.json|csv    every listed animal (all categories), newest first
  data/shelters.json|csv   every shelter with contact info and counts
  data/new.json            animals that appeared since the previous refresh
  data/changes.csv         running log of added/removed animals (timestamped)

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


def write(name, rows):
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

    write("animals", animals)
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
