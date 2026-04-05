"""
pipeline.py

This file connects the full backend flow:

question -> parser -> retrieval -> responder
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.core.schemas import StructuredWineQuery
from backend.services.parser.parser import parse_query
from backend.services.responder import build_response
from backend.services.retrieval import retrieve_wines


def _normalize_structured_query(
    parsed_output: StructuredWineQuery | dict[str, Any],
) -> StructuredWineQuery:
    """
    Normalize parser output into a StructuredWineQuery.
    """
    if isinstance(parsed_output, StructuredWineQuery):
        return parsed_output

    return StructuredWineQuery.model_validate(parsed_output)


def run_query_pipeline(
    question: str,
    df: pd.DataFrame,
    limit_override: int | None = None,
    page_override: int | None = None,
    page_size_override: int | None = None,
) -> dict[str, Any]:
    """
    Run the complete app pipeline for one user question.

    Flow:
    1. Parse natural-language question into StructuredWineQuery
    2. Apply API-level paging overrides
    3. Retrieve matching wines
    4. Build grounded response text
    5. Return final payload for the API
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    parsed_output = parse_query(question.strip())
    structured_query = _normalize_structured_query(parsed_output)

    # Collect updates in one place so we do one model_copy call.
    updates: dict[str, Any] = {}

    # Backward compatibility with the old API.
    # If limit_override is provided and page_size_override is not,
    # use limit as the page size for the first page.
    if limit_override is not None:
        updates["limit"] = limit_override
        if page_size_override is None:
            updates["page_size"] = min(limit_override, 20)

    if page_override is not None:
        updates["page"] = page_override

    if page_size_override is not None:
        updates["page_size"] = page_size_override

    if updates:
        structured_query = structured_query.model_copy(update=updates)

    retrieval_result = retrieve_wines(df, structured_query)
    final_response = build_response(structured_query, retrieval_result)

    return final_response