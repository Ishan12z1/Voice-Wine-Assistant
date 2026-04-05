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


class DatasetFilterOption(BaseModel):
    """
    One grounded selectable value for a dataset-backed filter.
    """
    value: str
    label: str
    count: int | None = None


class DatasetTextFilter(BaseModel):
    """
    Metadata for one text/categorical filter shown in the frontend.
    """
    field: str
    label: str
    input_type: str
    available_count: int = 0
    hint: str | None = None
    options: list[DatasetFilterOption] = Field(default_factory=list)


class DatasetNumericFilter(BaseModel):
    """
    Metadata for one numeric/range filter shown in the frontend.
    """
    field: str
    label: str
    min_value: float | int | None = None
    max_value: float | int | None = None
    step: float = 1.0
    unit: str | None = None


class FilterMetadataResponse(BaseModel):
    """
    Response body for the dynamic frontend filter panel.
    """
    dataset_path: str
    text_filters: list[DatasetTextFilter] = Field(default_factory=list)
    numeric_filters: list[DatasetNumericFilter] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """
    Response body for the health endpoint.
    """
    status: str
    rows_loaded: int
    columns_loaded: int
    dataset_path: str
