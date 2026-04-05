# Wine Info App - Version 1

Version 1 of the Wine Info App is a dataset-grounded wine search assistant that lets users explore a wine collection using plain English. It includes a FastAPI backend, a lightweight browser frontend, structured query parsing, deterministic filtering and ranking, and optional browser-based voice input and spoken responses.

## What Version 1 Includes

- Natural-language wine search such as:
  - `Best-rated red wines under $50`
  - `Show me Cabernet Sauvignon from California`
  - `Recommend a housewarming gift`
- A FastAPI backend with:
  - `GET /`
  - `GET /health`
  - `POST /query`
- Structured query parsing that can detect:
  - color
  - price range
  - country
  - region
  - appellation
  - producer
  - varietal
  - vintage range
  - ABV
  - bottle size
  - score thresholds
  - recommendation / gift intent
- Deterministic retrieval pipeline:
  - parse question
  - apply dataset-backed filters
  - rank results
  - generate grounded response text
- Ranking strategies for:
  - best rated
  - cheapest
  - most expensive
  - value-oriented recommendations
  - newest vintage
  - alphabetical browsing
- A frontend UI with:
  - typed search
  - example prompts
  - result cards with wine facts
  - follow-up suggestion chips
  - browser speech-to-text input
  - browser text-to-speech output
- Dataset-backed behavior only:
  - unsupported educational or invented-answer requests are rejected honestly
  - broad searches may ask the user to refine the request

## Current Project Structure

```text
backend/
  api/
    main.py
    models.py
  core/
    data_loader.py
    schemas.py
  services/
    parser.py
    pipeline.py
    retrieval.py
    filters.py
    ranking.py
    responder.py
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
requirements.txt
README.md
```

## How The App Works

Version 1 follows a simple grounded pipeline:

1. The user asks a question in the frontend or through the API.
2. The backend parser converts the question into a `StructuredWineQuery`.
3. Filters are applied against the processed wine dataset.
4. Matching wines are ranked according to the detected intent or sort mode.
5. The API returns:
   - a structured query payload
   - a grounded summary
   - a short spoken summary
   - wine result rows for the UI
6. The frontend renders the summary and matching wine cards.

## Dataset

The app currently loads its data from:

- `data/processed/wines_enriched.csv`

By default, the backend expects that file to exist. You can also override the dataset path with the `WINE_DATASET_PATH` environment variable.

## API Summary

### `GET /`
Quick check that the API is running.

### `GET /health`
Confirms the backend can load the dataset and returns row and column counts.

### `POST /query`
Main natural-language search endpoint.

Example request body:

```json
{
  "question": "Best-rated red wines under $50",
  "limit": 5
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

## How To Run Version 1

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

### 3. Start the backend API

From the project root:

```powershell
uvicorn backend.api.main:app --reload
```

The backend will start at:

- `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

### 4. Start the frontend

Open a second terminal in the project root and run:

```powershell
python -m http.server 5500 --directory frontend
```

Then open:

- `http://127.0.0.1:5500`

The frontend is already configured to call the backend at `http://127.0.0.1:8000`.

## Example Queries To Try

- `Best-rated red wines under $50`
- `Show me Cabernet Sauvignon from California`
- `Show Napa Valley wines with score above 92`
- `Cheapest white wine`
- `Most expensive bottle from Burgundy`
- `Recommend a housewarming gift`
- `Show me 750ml sparkling wines from Champagne`

## Notes About Version 1

- This is a local development version of the app.
- The frontend voice features depend on browser support for speech APIs.
- The app is intentionally dataset-grounded and does not invent tasting notes, food pairings, or general wine education answers.
- Broad requests may return a clarification prompt instead of a long unhelpful result list.

## Optional Health Check

Once the backend is running, you can verify it with:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

Or open the Swagger docs in the browser:

- `http://127.0.0.1:8000/docs`

## Version

This README documents:

- `Wine Info App - Version 1`
