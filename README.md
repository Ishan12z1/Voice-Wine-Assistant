# Wine Info App

Wine Info App is a dataset-grounded wine search assistant built with a FastAPI backend and a lightweight browser frontend. It lets users explore a wine collection using plain English, dynamic dataset-backed filters, deterministic ranking, and optional browser voice input and speech output.

The project is designed to stay honest to the underlying dataset. It does not invent unsupported wine facts, and it surfaces unresolved or unavailable requests explicitly when they do not match the active dataset.

link to video explanation : https://youtu.be/51c8n51nqWk

## Quick Start

For local development with one command:

```powershell
.\.venv\Scripts\python.exe .\run_dev.py
```

For the containerized demo:

```powershell
docker compose up --build
```

Open:

- local app: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

## Features

- Natural-language wine search
  - `Best-rated red wines under $50`
  - `Show me Cabernet Sauvignon from California`
  - `Recommend a housewarming gift`
  - `Show me wines with ABV above 14%`
- Dataset-grounded parsing and validation for:
  - color
  - country
  - region
  - appellation
  - producer
  - varietal
  - wine name
  - price range
  - vintage range
  - ABV
  - bottle size
  - score thresholds
  - occasion / recommendation intent
- Deterministic retrieval and ranking
- Grounded no-result handling and unresolved entity tracking
- Backend-driven follow-up suggestions
- Pagination and refinement support
- Dynamic frontend filter panel backed by dataset metadata
- Browser speech-to-text input
- Browser text-to-speech output

## How It Works

1. The user enters a question, clicks a follow-up suggestion, or applies the filter panel.
2. The backend parses the request into structured filters and intent.
3. Supported text fields are grounded against metadata built from the active processed dataset.
4. Deterministic retrieval applies filters and ranking.
5. The backend returns:
   - structured query information
   - grounded response text
   - spoken summary text
   - result rows
   - pagination metadata
   - follow-up suggestions
6. The frontend renders the answer, result cards, pagination controls, filter tools, and speech controls.

## API

### `GET /`
Serves the frontend app from the backend.

### `GET /health`
Confirms the backend can load the dataset and returns row and column counts.

### `GET /filters`
Returns metadata-backed filter options for the frontend.

The filter payload currently includes grounded text filters such as:

- `color`
- `country`
- `region`
- `producer`
- `varietal`

It also includes numeric ranges such as:

- `price`
- `abv`
- `vintage`

### `POST /query`
Main natural-language search endpoint.

Example request:

```json
{
  "question": "Best-rated red wines under $50",
  "page": 1,
  "page_size": 5
}
```

Example response fields:

- `query`
- `response_type`
- `summary`
- `spoken_summary`
- `applied_filters_text`
- `ranking_basis_text`
- `show_results`
- `total_matches`
- `returned_count`
- `wines`
- `page`
- `page_size`
- `total_pages`
- `has_next_page`
- `has_prev_page`
- `followup_suggestions`

## Frontend

The browser UI includes:

- typed query input
- example prompt chips
- a toggleable filter section
- grounded follow-up narrowing chips
- answer summary and result cards
- pagination controls
- visible speech controls on page load

### Filter Panel

The filter panel is:

- hidden by default
- opened by clicking `Show filters`
- populated dynamically from `GET /filters`
- collapsed again after `Ask` or `Apply filters`

This keeps available options aligned with the current dataset instead of hardcoded frontend values.

### Voice Features

The frontend supports:

- speech-to-text through `frontend/voice.js`
- text-to-speech through `frontend/tts.js`

Current behavior:

- speech controls are visible as soon as the page opens
- auto-speak works for fresh responses
- follow-up chip clicks can trigger the new answer speech
- pagination does not auto-speak on every page turn

Voice behavior still depends on browser support for speech APIs.

### Browser Support

Voice input and voice output rely on browser speech APIs.

Recommended browsers for the full voice experience:
- Google Chrome
- Microsoft Edge

In browsers with limited speech API support, the typed question workflow still works, but microphone input and spoken output may be unavailable or inconsistent.

## Dataset

The project uses:

- raw dataset: `data/raw/Assignment wine dataset - Sheet1.csv`
- processed runtime dataset: `data/processed/wines_enriched.csv`

By default, the backend loads the processed dataset. You can override the runtime dataset path with:

- `WINE_DATASET_PATH`

The backend now loads `.env` automatically from the repo root, and the active runtime dataset comes from `WINE_DATASET_PATH` there. The metadata layer is built from that same active processed dataset, so grounding, filter options, and suggestions stay aligned with the data the backend is actually using.

In Docker, the same `WINE_DATASET_PATH` value is passed into the container and resolves relative to `/app`, so `data/processed/wines_enriched.csv` continues to work there too.

### Assignment Source

This project uses the wine dataset provided in the assignment for Option B — Voice Wine Explorer.

In this repo:

- `data/raw/Assignment wine dataset - Sheet1.csv` is the local copy of the dataset given in the assignment
- `data/processed/wines_enriched.csv` is the processed runtime dataset derived from that source

The app stays grounded in this dataset pipeline. Query parsing, filtering, ranking, and responses are based only on the active dataset loaded by the backend, and unsupported facts are not invented.

### Refreshing The Dataset

If you update the raw CSV and want to rebuild the processed files in one step, run:

```powershell
.\scripts\refresh_dataset.ps1
```

This script:

- reads the raw CSV
- rebuilds `data/processed/wines_clean.csv`
- rebuilds `data/processed/wines_enriched.csv`
- relies on the backend's existing auto-refresh behavior for dataset metadata

You can also point it at custom paths:

```powershell
.\scripts\refresh_dataset.ps1 `
  -RawPath "data/raw/my_new_wines.csv" `
  -CleanPath "data/processed/my_clean.csv" `
  -EnrichedPath "data/processed/my_enriched.csv"
```

If you want the app to switch to a custom enriched dataset and persist that change in `.env`, run:

```powershell
.\scripts\refresh_dataset.ps1 `
  -EnrichedPath "data/processed/my_enriched.csv" `
  -UpdateEnv
```

If you write the enriched dataset to a non-default location without `-UpdateEnv`, the script prints the exact `WINE_DATASET_PATH="..."` line to place in `.env`.

## Docker

The backend now serves the frontend directly, so the containerized app only needs one service.

Build and run it with:

```powershell
docker compose up --build
```

Then open:

- `http://127.0.0.1:8000`

Useful routes:

- app UI: `/`
- API docs: `/docs`
- health: `/health`

Container notes:

- `.env` is loaded automatically inside the container
- `WINE_DATASET_PATH` controls which enriched CSV is active
- the frontend is served from FastAPI at `/`
- no separate frontend container or manual frontend server is required for the showcase path

## Project Structure

```text
backend/
  api/
    main.py
    models.py
  core/
    data_loader.py
    dataset_metadata.py
    schemas.py
  services/
    filters.py
    loader.py
    pipeline.py
    ranking.py
    responder.py
    retrieval.py
    parser/
      builders.py
      extractors.py
      matching.py
      parser.py
frontend/
  index.html
  app.js
  voice.js
  tts.js
  styles.css
data/
  raw/
  processed/
smoketest/
tests/
requirements.txt
README.md
run_dev.py
Dockerfile
docker-compose.yml
```

## Setup

### 0. Create the environment file

Copy `.env.example` to `.env` and keep the default dataset path unless you want to point to another processed dataset.

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Start the backend

```powershell
uvicorn backend.api.main:app --reload
```

Backend URLs:

- `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

The backend now serves the frontend too, so you can open `http://127.0.0.1:8000` directly.

### 4. Start the frontend separately (optional)

In a second terminal:

```powershell
python -m http.server 5500 --directory frontend
```

Then open:

- `http://127.0.0.1:5500`

The standalone frontend is configured to talk to the backend at `http://127.0.0.1:8000`.

### One-Command Local Startup

To launch both the backend and the standalone frontend dev server together, run:

```powershell
.\.venv\Scripts\python.exe .\run_dev.py
```

This starts:

- backend at `http://127.0.0.1:8000`
- frontend at `http://127.0.0.1:5500`

Press `Ctrl+C` once to stop both processes cleanly.

## Example Queries

- `Best-rated red wines under $50`
- `Show me Cabernet Sauvignon from California`
- `Show Napa Valley wines with score above 92`
- `Cheapest white wine`
- `Most expensive bottle from Burgundy`
- `Recommend a housewarming gift`
- `Show me 750ml sparkling wines from Champagne`
- `Show me wines with ABV above 14%`
- `Best red wine in India`
- `Show me dry red wines`

These examples cover both successful searches and grounded failure cases.

## Testing

### Smoke Tests

The `smoketest/` folder includes smoke-style scripts such as:

- `smoketest_v2_baseline.py`
- `smoketest_metadata.py`
- `smoketest_unresolved_entities.py`
- `smoketest_pagination_and_refinement.py`

Example runs:

```powershell
.\.venv\Scripts\python.exe -m smoketest.smoketest_v2_baseline
.\.venv\Scripts\python.exe -m smoketest.smoketest_metadata
.\.venv\Scripts\python.exe -m smoketest.smoketest_unresolved_entities
.\.venv\Scripts\python.exe -m smoketest.smoketest_pagination_and_refinement
```

### Layered Regression Tests

The `tests/` folder contains pytest-style tests for different logical layers:

- `test_loader_layer.py`
- `test_metadata_layer.py`
- `test_parser_layer.py`
- `test_pipeline_layer.py`
- `test_api_layer.py`
- `test_end_to_end_regressions.py`
- `test_grounded_query_logic.py`

These cover:

- raw-to-clean dataset processing
- metadata generation and refresh behavior
- parser extraction and grounding
- retrieval and pipeline logic
- API response behavior
- end-to-end grounded regressions

If `pytest` is installed in the environment, run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Notes

- The app is intentionally dataset-grounded.
- Unsupported or unavailable requests should return honest responses instead of invented answers.
- Dynamic filters and grounded matching depend on the processed dataset currently loaded by the backend.
- Frontend voice features depend on browser support for speech APIs.

## Future Scope

- Use an LLM-based intent routing layer to complement the current rule-based parser for harder or more ambiguous queries.
- Upgrade text-to-speech to a more natural voice stack so spoken answers feel less robotic and more production-ready.

## Versions

### Version 1

Version 1 established the core app foundation:

- FastAPI backend
- browser frontend
- natural-language wine search
- deterministic filtering and ranking
- basic voice input and speech output

### Version 2

Version 2 extended the project with:

- metadata-grounded validation
- unresolved entity tracking
- grounded no-result behavior
- pagination and refinement support
- backend-driven follow-up suggestions
- dynamic metadata-backed filter panel
- improved frontend speech and visibility behavior
- expanded smoke and regression test coverage
