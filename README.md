# kitties

Hourly snapshot of every animal up for adoption on [adopteereendier.be](https://www.adopteereendier.be),
plus all shelters. A GitHub Action runs `refresh.py` every hour and commits the results.

## Data (`data/`)

| File | Contents |
|---|---|
| `animals.csv` / `.json` | All listed animals (cats, dogs, farm animals, rabbits & rodents, other), newest first. `category` column to filter. |
| `per-soort/<categorie>.csv` / `.json` | Same, one file per category: `honden`, `katten`, `konijnen-en-knaagdieren`, `weidedieren`, `overigedieren`. |
| `shelters.csv` / `.json` | All shelters: address, phone, email, website, animal counts. |
| `new.json` | Animals that appeared since the previous hourly run. |
| `changes.csv` | Running log of every animal added/removed, with UTC timestamp. |
| `geocache.json` | Address → coordinates cache used by `geocode.py`. |

CSV files use `;` as separator and open directly in Excel. Git history = full history of the listings.

## Local use

```
python refresh.py                  # full refresh into data/ (~35 s)
python check_cats.py               # new cats since your last local check
python check_cats.py -c honden     # same for dogs (honden, weidedieren, konijnen-en-knaagdieren, overigedieren)
python geocode.py                  # (re)geocode data/shelters.json only
```

## Coordinates

Shelters are geocoded with the free Flemish government geocoder
([geo.api.vlaanderen.be](https://geo.api.vlaanderen.be/geolocation/v4/Location), no key). Results are cached
in `data/geocache.json`, so the hourly run only looks up new or changed addresses. Delete an entry there
to force a new lookup.

Shelters get `lat`, `lon` and `geo_precision`: `address` (house number), `street`, or `municipality`
(the site lists no street, or the street is unknown to the register, so it's the town centre). Animals get
their shelter's `lat`/`lon`.

No dependencies beyond the Python standard library.

## Using the data in an app

Everything in `data/` is served via GitHub Pages (CDN, CORS enabled):

```
https://hansf.github.io/kitties/data/meta.json        <- start here
https://hansf.github.io/kitties/data/animals.json
https://hansf.github.io/kitties/data/per-soort/katten.json
https://hansf.github.io/kitties/data/shelters.json
https://hansf.github.io/kitties/data/new.json
```

`meta.json` holds `updated_at` (last time the data actually changed), counts per category and the URL
of every file. Poll it (hourly is plenty) and only re-download the data when `updated_at` changes.

Each animal: `category, id, type, name, breed, sex, age, summary, shelter, location, lat, lon, badge, image, url`.
Join animals to shelters on `shelter` == `name`.
