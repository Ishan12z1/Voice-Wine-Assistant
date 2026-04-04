"""
models.py

This file defines the request and response models used by the FastAPI layer.

Why this file exists:
- It keeps HTTP payload validation separate from business logic.
- It makes the API contract explicit.
- It helps the frontend know exactly what the backend returns.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WineQueryRequest(BaseModel):
    """
    Request body for the main wine query endpoint.
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(..., min_length=1, description="Natural-language wine question")
    limit: int | None = Field(default=None, ge=1, le=50, description="Optional override for result count")


class WineQueryResponse(BaseModel):
    """
    Response body returned by the main wine query endpoint.
    """
    model_config = ConfigDict(extra="allow")

    query: dict[str, Any]
    response_type: str
    summary: str
    spoken_summary: str
    applied_filters_text: str
    ranking_basis_text: str
    show_results: bool

    total_matches: int
    returned_count: int
    wines: list[dict[str, Any]]

    message: str | None = None


class HealthResponse(BaseModel):
    """
    Response body for the health endpoint.
    """
    status: str
    rows_loaded: int
    columns_loaded: int
    dataset_path: str