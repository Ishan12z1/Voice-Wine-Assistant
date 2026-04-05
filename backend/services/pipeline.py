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

    This accepts either:
    - an already-built StructuredWineQuery
    - a plain dict that matches the schema

    Keeping this helper makes the pipeline a little more future-proof even
    though the parser currently returns StructuredWineQuery directly.
    """
    if isinstance(parsed_output, StructuredWineQuery):
        return parsed_output

    return StructuredWineQuery.model_validate(parsed_output)


def run_query_pipeline(
    question: str,
    df: pd.DataFrame,
    limit_override: int | None = None,
) -> dict[str, Any]:
    """
    Run the complete app pipeline for one user question.

    Flow:
    1. Parse natural-language question into StructuredWineQuery
    2. Retrieve matching wines
    3. Build grounded response text
    4. Return final payload for the API
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    # Parse the question using the app's single parser entrypoint.
    parsed_output = parse_query(question.strip())
    structured_query = _normalize_structured_query(parsed_output)

    # Allow API callers to override the result limit without modifying parser logic.
    if limit_override is not None:
        structured_query = structured_query.model_copy(update={"limit": limit_override})

    retrieval_result = retrieve_wines(df, structured_query)
    final_response = build_response(structured_query, retrieval_result)

    return final_response