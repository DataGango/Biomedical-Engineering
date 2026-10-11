# Biomedical Literature Dashboard

## Overview

Fieldnotes is a local dashboard for discovering recent biomedical publications and abstracts. It includes preset searches for Nature, medical research, and bioengineering, plus persistent custom searches that users can add from the dashboard.

The dashboard fetches publication records through the Europe PMC REST API. Europe PMC indexes PubMed records and other biomedical literature. A record can include title, authors, journal, year, DOI, abstract, keywords, publication type, and source links.

## Current capabilities

- Searches records from the last 365 days for Nature, medical research, and bioengineering.
- Lets users add and name a custom Europe PMC query.
- Saves custom searches and latest results in SQLite.
- Runs an initial extraction when a custom search is added.
- Refreshes saved searches every 48 hours while the dashboard server is running.
- Checks for due searches every minute; open dashboards poll for updated saved-search results every minute.
- Shows matching-record, fetched-record, and abstract counts separately.
- Displays abstracts, citations, PubMed or Europe PMC links, and DOI links when available.
- Links to a dedicated robotic-surgery research page with an all-years publication query and recent official Nobel medicine prize records.
- Provides a robotic surgery research page at `/robotic-surgery`, with an all-years Europe PMC search and a separate feed of recent Nobel Prize in Physiology or Medicine awards.

## Technology and RAG status

- Python standard library `http.server` serves the dashboard and JSON API.
- Python `urllib` sends HTTP requests to Europe PMC.
- Python `urllib` retrieves official Nobel Prize open API data.
- Python `urllib` also retrieves official Nobel Prize open API award records.
- SQLite (`sqlite3`) stores saved searches and cached results.
- A Python background thread checks saved searches for due refreshes.
- HTML, CSS, and vanilla JavaScript implement the interface.

**Important:** The project has a separate `BiomedicalAgent` and `Retriever`, but the current dashboard search flow does not call them. The retriever is a simple local keyword-overlap baseline, not embedding/vector RAG. The dashboard searches Europe PMC directly and displays source-provided records; it does not use an LLM to summarize, synthesize, or answer questions. Therefore, it avoids LLM-generated factual claims in this workflow, but this is not a guarantee that source publications themselves are correct. Verify findings in the linked paper.

The current global search means user-defined queries over Europe PMC's index. It does not search every biomedical database, use semantic ranking, or generate queries with an AI model.

## Files

- `dashboard.py`: local web server, preset queries, and JSON API routes.
- `dashboard.html`: page structure and controls.
- `dashboard.css`: styling and responsive layouts.
- `dashboard.js`: search requests, result rendering, counts, filtering, saved-search tabs, and polling.
- `saved_searches.py`: SQLite persistence, refresh schedule, and result refresh logic.
- `nobel.py`: adapter for official Nobel Prize in Physiology or Medicine records.
- `robotic_surgery.html`, `robotic_surgery.css`, `robotic_surgery.js`: robotic surgery literature and Nobel medicine page.
- `pubmed.py`: Europe PMC and NCBI PubMed clients and publication parsers.
- `nobel.py`: normalizes official Nobel Prize in Physiology or Medicine award records and source links.
- `robotic_surgery.html`, `robotic_surgery.css`, `robotic_surgery.js`: robotic-surgery research interface, publication cards, and Nobel award cards.
- `agent.py`: evidence retrieval helper; separate from the dashboard's Europe PMC query path.
- `../rag/retriever.py`: lightweight keyword-based local retriever used by the evidence helper.
- `../tests/test_pubmed.py`: provider and publication parser tests.
- `../tests/test_saved_searches.py`: saved-search persistence and scheduling tests.

## Run locally

From the project root:

```sh
python -m biomedical.dashboard --port 8765
```

Open `http://127.0.0.1:8765/`. Choose another port if that one is already occupied. Keep the server running for automatic refreshes.

The default database is `data/biomedical_searches.sqlite3`. Set `BIOMEDICAL_SEARCH_DB` to use another SQLite file:

```sh
BIOMEDICAL_SEARCH_DB=/path/to/biomedical_searches.sqlite3 python -m biomedical.dashboard --port 8765
```

## Add a global search

In the **Add global search** form, enter a name (up to 80 characters) and a Europe PMC query (up to 300 characters), then select **Save & extract**. Results are extracted immediately and saved locally.

Example Europe PMC query syntax:

```text
(neural interface OR brain-computer interface) AND stroke
```

```text
(CRISPR OR gene editing) AND cancer
```

Custom searches use the provider's default limit of 10 records. The per-category selector controls the number fetched for built-in searches.

## API

- `GET /api/search?category=nature|medical|bioengineering&limit=10&q=optional-terms`: search a built-in category. `limit` must be 1-30; optional terms are limited to 200 characters.
- `GET /robotic-surgery`: open the robotic procedure research page.
- `GET /api/robotic-surgery?years=all&limit=20&q=optional-terms`: search indexed robotic-procedure papers. `years=all` omits the publication-date filter; values from 1 to 120 select a rolling year window.
- `GET /api/nobel-medicine?limit=10`: retrieve recent Physiology or Medicine prize records from Nobel Prize open data.
- `GET /api/searches`: list saved searches and latest results.
- `GET /api/robotic-surgery?years=all&limit=20&q=optional-terms`: search indexed robotic procedure research. `years=all` omits the publication date filter; numeric values from 1 to 120 specify a rolling year window.
- `GET /api/nobel-medicine?limit=10`: retrieve recent Physiology or Medicine prize records from the official Nobel Prize API.
- `POST /api/searches`: save and immediately run a custom search. JSON body: `{"name":"Neural interfaces","query":"neural interface"}`.
- `POST /api/searches/<id>/refresh`: immediately refresh one saved query.

Invalid custom names or queries are rejected. Search details and results live in the configured SQLite database.

## Refresh behavior

A successful refresh records its timestamp and schedules the next refresh 48 hours later. The scheduler checks every 60 seconds. If a refresh fails, the error is stored and a retry is scheduled after 15 minutes; the prior successful results are retained. The scheduler is in-process: it pauses when the dashboard server stops and resumes when it starts again.

Built-in category searches load on page load and manual refresh; they are not persisted and are not part of the 48-hour scheduler.

## Understanding the counts and links

- **Matching in Europe PMC**: total hits reported by the provider for the query and date range.
- **Records extracted**: records fetched for display, capped by the selected result limit.
- **Abstracts available**: fetched records with a non-empty abstract.
- Paper links go to PubMed when a PMID is present, otherwise to Europe PMC. A DOI link appears when available.

These counts differ because only a limited page of results is fetched and some records have no abstract.

## Tests

Run the focused tests with the project's configured Python environment and pytest installed:

```sh
python -m pytest tests/test_saved_searches.py tests/test_pubmed.py -q
```

Tests use fake provider responses and temporary SQLite databases; live Europe PMC access is not required.

## Limitations

- Coverage depends on Europe PMC; other sources such as Crossref, Semantic Scholar, and publisher APIs are not independently queried.
- The robotic-surgery page reports matching indexed records, fetches a bounded page of abstracts, and links to source records; it is not a clinically complete catalog of every procedure or every publication. The Nobel section shows recent prizes in Physiology or Medicine broadly. It does not imply that those prizes were awarded for robotic surgery; robotic surgery has no dedicated Nobel category.
- The robotic procedure search retrieves matching indexed research, not a clinically complete catalog of every operation or every paper ever published. Nobel medicine prizes cover the full field of physiology or medicine and are not necessarily related to robotic surgery.
- Search is provider-query based, not semantic or LLM-powered.
- The 48-hour scheduler runs only while this local server process is active. Use a persistent scheduler such as macOS `launchd`/cron or a hosted scheduled job if it must run while the dashboard is stopped.
- SQLite is intended for local, single-user use. A hosted multi-user service would need authentication, access controls, managed persistence, and request protections.
- The dashboard supports research discovery, not diagnosis or treatment recommendations. Check claims in the source publication and consult qualified health professionals for medical decisions.
