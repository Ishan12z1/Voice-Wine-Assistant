"""
models.py

This file defines the request and response models used by the FastAPI layer.
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

    # Backward-compatible override for old callers.
    limit: int | None = Field(default=None, ge=1, le=50, description="Optional override for result count")

    # Phase 3 pagination fields.
    page: int = Field(default=1, ge=1, description="Page number to return")
    page_size: int = Field(default=10, ge=1, le=20, description="Number of wines per page")


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

    # Pagination metadata
    page: int
    page_size: int
    total_pages: int
    has_next_page: bool
    has_prev_page: bool

    message: str | None = None
    followup_suggestions: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """
    Response body for the health endpoint.
    """
    status: str
    rows_loaded: int
    columns_loaded: int
    dataset_path: str
