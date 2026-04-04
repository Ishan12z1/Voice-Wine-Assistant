"""
retrieval.py

This file coordinates the full Step 5 retrieval pipeline. It takes a
StructuredWineQuery , filters the dataset, ranks the matching wines,
applies the requested limit, and returns JSON-friendly results.

"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.core.schemas import QueryIntent, StructuredWineQuery
from backend.services.filters import retrieve_filtered_wines
from backend.services.ranking import rank_wines


def _to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Convert a DataFrame to JSON-friendly records.

    Pandas NaN values are replaced with None so FastAPI/JSON output is cleaner.
    """
    cleaned = df.where(pd.notnull(df), None)
    return cleaned.to_dict(orient="records")


def retrieve_wines(df: pd.DataFrame, query: StructuredWineQuery) -> dict[str, Any]:
    """
    Run the complete Step 5 retrieval pipeline.

    Flow:
    1. Short-circuit unsupported or ambiguous requests
    2. Apply dataset filters
    3. Rank the filtered wines
    4. Limit the output
    5. Return records plus metadata
    """
    if query.intent == QueryIntent.UNSUPPORTED_REQUEST:
        return {
            "query": query.model_dump(),
            "total_matches": 0,
            "returned_count": 0,
            "wines": [],
            "message": query.unsupported_reason or "This request is not supported by the dataset.",
        }

    if query.needs_clarification:
        return {
            "query": query.model_dump(),
            "total_matches": 0,
            "returned_count": 0,
            "wines": [],
            "message": query.clarification_message or "More detail is needed to search the collection.",
        }

    filtered_df = retrieve_filtered_wines(df=df, query=query)
    total_matches = len(filtered_df)

    ranked_df = rank_wines(df=filtered_df, query=query)

    limit = query.limit if query.limit > 0 else 10
    limited_df = ranked_df.head(limit).reset_index(drop=True)

    return {
        "query": query.model_dump(),
        "total_matches": total_matches,
        "returned_count": len(limited_df),
        "wines": _to_records(limited_df),
        "message": None if total_matches > 0 else "No wines matched the requested filters.",
    }