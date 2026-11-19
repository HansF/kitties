"""Check adopteereendier.be for newly listed animals (default: cats).

Usage:
    python check_cats.py            # show cats new since last run (first run: latest page)
    python check_cats.py --pages 3  # on first run / with --all, how many pages to show
    python check_cats.py --all      # ignore saved state, just list the latest pages
    python check_cats.py -c honden  # other category: honden, weidedieren,
                                    # konijnen-en-knaagdieren, overigedieren

State (IDs already seen) is kept in seen.json (cats) / seen_<category>.json.
"""
import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

SITE = "https://www.adopteereendier.be"
MAX_PAGES = 20  # safety cap when walking back to the last seen cat

def card_re(category):
    return re.compile(
        r'<a href="(?P<url>https://www\.adopteereendier\.be/' + re.escape(category)
        + r'/(?:(?P<type>[a-z-]+)/)?(?P<id>\d+)/[^"]+)">(?P<body>.*?)</a>',
        re.S,
    )


def state_file(category):
    name = "seen.json" if category == "katten" else f"seen_{category}.json"
    return Path(__file__).with_name(name)


def text(fragment):
    fragment = re.sub(r"<!--.*?-->", "", fragment, flags=re.S)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def parse_card(m):
    body = m.group("body")
    ps = re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)
    img = re.search(r"url\('([^']+)'\)", body)
    badge = re.search(r'rounded bg-color2">(.*?)</div>', body, re.S)
    name = re.search(r"<h4[^>]*>(.*?)</h4>", body, re.S)
    p = [text(x) for x in ps]
    sex_age = p[1].split(" - ", 1) if len(p) > 1 else ["", ""]
    return {
        "id": int(m.group("id")),
        "type": m.group("type") or "",
        "name": text(name.group(1)) if name else "",
        "breed": p[0] if p else "",
        "sex": sex_age[0],
        "age": sex_age[1] if len(sex_age) > 1 else "",
        "summary": p[2] if len(p) > 2 else "",
        "shelter": p[3] if len(p) > 3 else "",
        "location": p[4] if len(p) > 4 else "",
        "badge": text(badge.group(1)) if badge else "",
        "image": img.group(1) if img else "",
        "url": m.group("url"),
    }


def fetch_page(category, n):
    req = urllib.request.Request(f"{SITE}/{category}?page={n}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    return [parse_card(m) for m in card_re(category).finditer(page)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--category", default="katten")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    args = ap.parse_args()

    STATE = state_file(args.category)
    seen = set() if args.all or not STATE.exists() else set(json.loads(STATE.read_text()))
    first_run = not seen

    cats, n = [], 1
    while True:
        page = fetch_page(args.category, n)
        if not page:
            break
        cats.extend(page)
        if first_run and n >= args.pages:
            break
        if not first_run and any(c["id"] in seen for c in page):
            break
        if not first_run and n >= MAX_PAGES:
            break
        n += 1

    new = [c for c in cats if c["id"] not in seen]

    if not args.all:
        STATE.write_text(json.dumps(sorted(seen | {c["id"] for c in cats})))

    if args.json:
        json.dump(new, sys.stdout, ensure_ascii=False, indent=2)
        return
    label = f"Latest {args.category}" if first_run else "New since last check"
    print(f"{label}: {len(new)}\n")
    for c in new:
        badge = f" [{c['badge']}]" if c["badge"] else ""
        kind = f" ({c['type']})" if c["type"] else ""
        print(f"#{c['id']}  {c['name']}{kind}{badge}")
        print(f"    {c['breed']} | {c['sex']} | {c['age']}")
        print(f"    {c['shelter']} ({c['location']})")
        print(f"    {c['summary']}")
        print(f"    {c['url']}\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
