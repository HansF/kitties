"""Scrape all shelters from adopteereendier.be/dierenasielen into shelters.csv / shelters.json."""
import csv
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://www.adopteereendier.be/dierenasielen"
OUT = Path(__file__).parent

CARD_RE = re.compile(r'<div class="flex flex-col border border-color5">(.*?)Andere<br />\s*(\S+)', re.S)


def text(s):
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    lines = [re.sub(r"\s+", " ", html.unescape(l)).strip() for l in s.split("\n")]
    return [l for l in lines if l]


def count(label, body):
    m = re.search(label + r"<br />\s*(\S+)", body)
    return int(m.group(1)) if m and m.group(1).isdigit() else 0


def parse(body, other):
    name = re.search(r"<h4[^>]*>(.*?)</h4>", body, re.S)
    link = re.search(r'href="(https://www\.adopteereendier\.be/dierenasielen/([^/"]+)/[^"]+)"', body)
    logo = re.search(r'<img src="([^"]+)"', body)
    ps = re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)
    addr = text(ps[0]) if ps else []
    contact = ps[1] if len(ps) > 1 else ""
    email = re.search(r'href="mailto:([^"]+)"', contact)
    site = re.search(r'href="(https?://[^"]+)"', contact)
    phone = [l for l in text(contact) if l not in ("Mail ons", "Bezoek onze website")]
    postal = re.match(r"(\d{4})\s+(.*)", addr[-1]) if addr else None
    return {
        "name": " ".join(text(name.group(1))) if name else "",
        "province": link.group(2) if link else "",
        "street": ", ".join(addr[:-1]),
        "postcode": postal.group(1) if postal else "",
        "city": postal.group(2) if postal else (addr[-1] if addr else ""),
        "phone": " / ".join(phone),
        "email": email.group(1) if email else "",
        "website": site.group(1) if site else "",
        "dogs": count("Honden", body),
        "cats": count("Katten", body),
        "other": int(other) if other.isdigit() else 0,
        "url": link.group(1) if link else "",
        "logo": logo.group(1) if logo else "",
    }


def fetch(n):
    req = urllib.request.Request(f"{BASE}?page={n}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def scrape():
    shelters, seen, n = [], set(), 1
    while True:
        page = [parse(b, o) for b, o in CARD_RE.findall(fetch(n))]
        page = [s for s in page if s["url"] not in seen]
        if not page:
            break
        seen.update(s["url"] for s in page)
        shelters.extend(page)
        n += 1
    return shelters


def main():
    shelters = scrape()
    (OUT / "shelters.json").write_text(json.dumps(shelters, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "shelters.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(shelters[0]), delimiter=";")
        w.writeheader()
        w.writerows(shelters)
    print(f"{len(shelters)} shelters")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
