"""
retrieval.py
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.core.schemas import QueryIntent, StructuredWineQuery
from backend.services.filters import retrieve_filtered_wines
from backend.services.ranking import rank_wines

TOO_MANY_MATCHES_HARD_LIMIT = 250
TOO_MANY_MATCHES_SOFT_LIMIT = 100


def _clean_scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    return value


def _normalize_wine_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean_scalar(record.get("Id", record.get("id"))),
        "name": _clean_scalar(record.get("Name", record.get("name"))),
        "producer": _clean_scalar(record.get("Producer", record.get("producer"))),
        "country": _clean_scalar(record.get("Country", record.get("country"))),
        "region": _clean_scalar(record.get("Region", record.get("region"))),
        "appellation": _clean_scalar(record.get("Appellation", record.get("appellation"))),
        "varietal": _clean_scalar(record.get("Varietal", record.get("varietal"))),
        "color": _clean_scalar(record.get("color", record.get("Color"))),
        "price": _clean_scalar(record.get("Retail", record.get("price"))),
        "vintage": _clean_scalar(record.get("Vintage", record.get("vintage"))),
        "abv": _clean_scalar(record.get("ABV", record.get("abv"))),
        "volume_ml": _clean_scalar(record.get("volume_ml")),
        "best_score": _clean_scalar(record.get("best_score")),
        "avg_score": _clean_scalar(record.get("avg_score")),
        "rating_count": _clean_scalar(record.get("rating_count")),
        "image_url": _clean_scalar(record.get("image_url")),
        "reference_url": _clean_scalar(record.get("reference_url")),
    }


def _to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    cleaned_df = df.where(pd.notnull(df), None)
    raw_records = cleaned_df.to_dict(orient="records")
    return [_normalize_wine_record(record) for record in raw_records]


def _should_require_refinement(query: StructuredWineQuery, total_matches: int) -> bool:
    """
    Ask the user to narrow the query when the result set is too broad.

    Rules:
    - always refine if the match count is extremely large
    - refine broad browse queries if there are too many matches and too few filters
    """
    active_filter_count = len(query.active_filters())

    if total_matches > TOO_MANY_MATCHES_HARD_LIMIT:
        return True

    if (
        query.intent == QueryIntent.BROWSE_COLLECTION
        and total_matches > TOO_MANY_MATCHES_SOFT_LIMIT
        and active_filter_count <= 1
    ):
        return True

    return False


def retrieve_wines(df: pd.DataFrame, query: StructuredWineQuery) -> dict[str, Any]:
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

    if _should_require_refinement(query, total_matches):
        return {
            "query": query.model_dump(),
            "total_matches": total_matches,
            "returned_count": 0,
            "wines": [],
            "message": (
                f"I found {total_matches} matching wines. "
                "Please narrow the search with one more detail like budget, color, "
                "country, region, producer, or varietal."
            ),
            "needs_refinement": True,
        }

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