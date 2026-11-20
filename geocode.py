"""Geocode shelter addresses with the Flemish government geocoder (geo.api.vlaanderen.be).

Free, no API key, covers every address in Flanders (all adopteereendier.be shelters are there).
Results are cached in data/geocache.json, keyed by the address string, so each address is
looked up once; a refresh only hits the API for new or changed addresses.

Each shelter gets:
  lat, lon        WGS84 coordinates (empty if nothing was found)
  geo_precision   "address" (house number), "street", "municipality" or "" (not found)

Usage:
  python geocode.py      geocode data/shelters.json in place and rewrite the data files
"""
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://geo.api.vlaanderen.be/geolocation/v4/Location"
CACHE = Path(__file__).parent / "data" / "geocache.json"
HEADERS = {"User-Agent": "kitties-geocoder/1.0"}
PAUSE = 0.2  # seconds between API calls, be polite


def _query(q):
    url = f"{API}?{urllib.parse.urlencode({'q': q, 'c': 1})}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=20) as r:
        hits = json.load(r).get("LocationResult") or []
    time.sleep(PAUSE)
    return hits[0] if hits else None


def _precision(location_type):
    t = (location_type or "").lower()
    if "huisnummer" in t or "adres" in t:
        return "address"
    if "straat" in t:
        return "street"
    return "municipality"


def _cities(city):
    """'ANTWERPEN (EKEREN)' -> ['EKEREN', 'ANTWERPEN']; 'GENT' -> ['GENT']."""
    m = re.match(r"\s*(.*?)\s*\((.*?)\)\s*$", city or "")
    return [m.group(2), m.group(1)] if m else [city.strip()] if city and city.strip() else []


def _split_street(street):
    """'BRUGGESTRAAT 200 A' -> ('BRUGGESTRAAT', ['200A', '200']); 'BAUDELOKAAI 13/001' -> (.., ['13'])."""
    m = re.match(r"^(.*?\D)\s*(\d+)\s*([A-Za-z]{1,3})?\b.*$", street or "")
    if not m:
        return (street or "").strip(), []
    name, num, letter = m.group(1).strip(), m.group(2), (m.group(3) or "").upper()
    numbers = [num + letter, num] if letter and letter != "BIS" else [num]
    return name, numbers


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower())


def _candidates(street, postcode, city):
    """(query, street name a hit must match or None) from most to least precise."""
    name, numbers = _split_street(street)
    qs = []
    if name:
        for c in _cities(city):
            qs += [(f"{name} {n}, {postcode} {c}", name) for n in numbers]
            qs += [(f"{name} {n}, {c}", name) for n in numbers]  # postcode on the site is sometimes off
            qs.append((f"{name}, {postcode} {c}", name))
    for c in _cities(city):
        qs += [(f"{postcode} {c}".strip(), None), (c, None)]
    if postcode:
        qs.append((postcode, None))
    return list(dict.fromkeys(q for q in qs if q[0]))


def key(shelter):
    return " | ".join(shelter.get(f, "").strip().upper() for f in ("street", "postcode", "city"))


def lookup(street, postcode, city):
    """Best hit for an address as {lat, lon, geo_precision, matched}, or None. Raises on network errors."""
    for q, street_name in _candidates(street, postcode, city):
        hit = _query(q)
        # the geocoder fuzzy-matches: "Bruggestraat, Oedelem" can come back as "Oedelemsteenweg"
        if hit and street_name and _norm(hit.get("Thoroughfarename")) != _norm(street_name):
            hit = None
        # town-only queries must land on a town, not on a look-alike street ("BETEKOM" -> Betekomsesteenweg)
        if hit and not street_name and hit.get("Thoroughfarename"):
            hit = None
        if hit:
            loc = hit["Location"]
            return {
                "lat": round(loc["Lat_WGS84"], 6),
                "lon": round(loc["Lon_WGS84"], 6),
                "geo_precision": _precision(hit.get("LocationType")),
                "matched": hit.get("FormattedAddress", ""),
            }
    return None


def add_coordinates(shelters):
    """Add lat/lon/geo_precision to each shelter dict in place, using and updating the cache.

    Network errors never fail the caller: the shelter just stays without coordinates and is
    retried on the next run (only definitive "not found" answers are cached).
    """
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    looked_up = failed = 0
    for s in shelters:
        k = key(s)
        if k not in cache:
            try:
                cache[k] = lookup(s.get("street", ""), s.get("postcode", ""), s.get("city", ""))
                looked_up += 1
            except Exception as e:  # noqa: BLE001 - keep the refresh going
                print(f"geocode failed for {k!r}: {e}")
                failed += 1
        hit = cache.get(k) or {}
        s["lat"] = hit.get("lat", "")
        s["lon"] = hit.get("lon", "")
        s["geo_precision"] = hit.get("geo_precision", "")
    if looked_up:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1),
                         encoding="utf-8", newline="\n")
    print(f"geocode: {looked_up} looked up, {failed} failed, {len(shelters) - looked_up - failed} cached")
    return shelters


if __name__ == "__main__":
    import refresh

    path = refresh.DATA / "shelters.json"
    shelters = add_coordinates(json.loads(path.read_text(encoding="utf-8")))
    refresh.write("shelters", shelters)
    missing = [s["name"] for s in shelters if s["lat"] == ""]
    print(f"{len(shelters) - len(missing)}/{len(shelters)} shelters have coordinates")
    for name in missing:
        print("  no coordinates:", name)
