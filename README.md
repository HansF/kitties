# kitties

Hourly snapshot of every animal up for adoption on [adopteereendier.be](https://www.adopteereendier.be),
plus all shelters. A GitHub Action runs `refresh.py` every hour and commits the results.

## Data (`data/`)

| File | Contents |
|---|---|
| `animals.csv` / `.json` | All listed animals (cats, dogs, farm animals, rabbits & rodents, other), newest first. `category` column to filter. |
| `shelters.csv` / `.json` | All shelters: address, phone, email, website, animal counts. |
| `new.json` | Animals that appeared since the previous hourly run. |
| `changes.csv` | Running log of every animal added/removed, with UTC timestamp. |

CSV files use `;` as separator and open directly in Excel. Git history = full history of the listings.

## Local use

```
python refresh.py                  # full refresh into data/ (~35 s)
python check_cats.py               # new cats since your last local check
python check_cats.py -c honden     # same for dogs (honden, weidedieren, konijnen-en-knaagdieren, overigedieren)
```

No dependencies beyond the Python standard library.
