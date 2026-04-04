"""
main.py

This file exposes the FastAPI application for the wine assistant backend.
It provides:
- a health endpoint to verify the service is up
- a query endpoint that runs the full Step 4 -> Step 5 -> Step 6 pipeline

Why this file exists:
- It turns the backend into a real HTTP service.
- It keeps the API layer thin and delegates business logic to services.
- It prepares the project for frontend or voice-client integration.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.models import HealthResponse, WineQueryRequest, WineQueryResponse
from backend.core.data_loader import DEFAULT_DATASET_PATH, load_wine_dataset
from backend.services.pipeline import run_query_pipeline

app = FastAPI(
    title="Voice Wine Assistant API",
    version="0.1.0",
    description="Dataset-grounded wine query backend",
)

# Allow frontend apps to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """
    Simple root endpoint so you can quickly confirm the API is running.
    """
    return {
        "message": "Voice Wine Assistant API is running.",
        "docs": "/docs",
        "health": "/health",
        "query_endpoint": "/query",
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health_check() -> HealthResponse:
    """
    Health endpoint used to confirm the backend can load the dataset.
    """
    dataset_path = os.getenv("WINE_DATASET_PATH", DEFAULT_DATASET_PATH)
    df = load_wine_dataset(dataset_path)

    return HealthResponse(
        status="ok",
        rows_loaded=len(df),
        columns_loaded=len(df.columns),
        dataset_path=dataset_path,
    )


@app.post("/query", response_model=WineQueryResponse, tags=["query"])
def query_wines(payload: WineQueryRequest) -> WineQueryResponse:
    """
    Main endpoint for natural-language wine search.

    Example input:
    {
        "question": "Best-rated red wines under $50",
        "limit": 5
    }
    """
    dataset_path = os.getenv("WINE_DATASET_PATH", DEFAULT_DATASET_PATH)

    try:
        df = load_wine_dataset(dataset_path)
        response_payload = run_query_pipeline(
            question=payload.question,
            df=df,
            limit_override=payload.limit,
        )
        return WineQueryResponse.model_validate(response_payload)

    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    except ValueError as exc:
        # Used for bad request inputs such as blank questions.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except RuntimeError as exc:
        # Used for internal integration issues, such as missing parser wiring.
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    except Exception as exc:
        # Final safety net so the API fails cleanly instead of crashing noisily.
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error: {exc}",
        ) from exc