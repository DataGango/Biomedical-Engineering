# Biomedical Engineering Research Dashboard

Fieldnotes is a biomedical literature discovery dashboard. It searches Europe PMC and displays source-linked publication records and abstracts. The dashboard includes all-fields discovery, Robotic Surgery research, Oncology, and Neurosurgery pages.

## Run locally

Requires Python 3.10 or later. The dashboard uses Python's standard library; `pytest` is only needed to run tests.

```sh
python -m biomedical.dashboard --port 8765
```

Open `http://127.0.0.1:8765/`. The home page links to the specialty pages. If port 8765 is occupied, select another port.

## Research pages

- `/`: recent Nature, medical, and bioengineering records; save custom Europe PMC searches.
- `/robotic-surgery`: robotic-surgery literature and official Nobel Prize in Physiology or Medicine records.
- `/oncology`: cancer and oncology literature search.
- `/neurosurgery`: neurosurgical, brain-surgery, and spine-surgery literature search.

Specialty searches support optional keywords, publication periods, and result limits. Results are citations and abstracts fetched from Europe PMC, not medical recommendations. Verify findings in the linked source publication.

## Tests

```sh
python -m pip install -r requirements.txt
python -m pytest
```

## Data and privacy

Saved searches are stored locally in `data/biomedical_searches.sqlite3` by default. Set `BIOMEDICAL_SEARCH_DB` to use a different path. Runtime databases and Python cache files are excluded from Git.
