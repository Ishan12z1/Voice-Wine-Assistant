"""
main.py

This file exposes the FastAPI application for the wine assistant backend.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.models import (
    FilterMetadataResponse,
    HealthResponse,
    WineQueryRequest,
    WineQueryResponse,
)
from backend.core.data_loader import load_wine_dataset
from backend.core.dataset_metadata import get_filter_panel_metadata
from backend.core.settings import get_configured_dataset_path, load_project_env
from backend.services.pipeline import run_query_pipeline

load_project_env()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="Voice Wine Assistant API",
    version="0.1.0",
    description="Dataset-grounded wine query backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health_check() -> HealthResponse:
    """
    Health endpoint used to confirm the backend can load the dataset.
    """
    dataset_path = get_configured_dataset_path()
    df = load_wine_dataset(dataset_path)

    return HealthResponse(
        status="ok",
        rows_loaded=len(df),
        columns_loaded=len(df.columns),
        dataset_path=dataset_path,
    )


@app.get("/filters", response_model=FilterMetadataResponse, tags=["meta"])
def get_filters() -> FilterMetadataResponse:
    """
    Metadata-backed filter options for the frontend.
    """
    dataset_path = get_configured_dataset_path()
    filter_payload = get_filter_panel_metadata(dataset_path)
    return FilterMetadataResponse.model_validate(filter_payload)


@app.post("/query", response_model=WineQueryResponse, tags=["query"])
def query_wines(payload: WineQueryRequest) -> WineQueryResponse:
    """
    Main endpoint for natural-language wine search.

    Example input:
    {
        "question": "Best-rated red wines under $50",
        "page": 1,
        "page_size": 10
    }
    """
    dataset_path = get_configured_dataset_path()

    try:
        df = load_wine_dataset(dataset_path)
        response_payload = run_query_pipeline(
            question=payload.question,
            df=df,
            limit_override=payload.limit,
            page_override=payload.page,
            page_size_override=payload.page_size,
        )
        return WineQueryResponse.model_validate(response_payload)

    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error: {exc}",
        ) from exc


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
