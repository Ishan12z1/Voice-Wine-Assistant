"""
retrieval.py
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from backend.core.schemas import QueryIntent, StructuredWineQuery, UnresolvedReason
from backend.services.filters import retrieve_filtered_wines
from backend.services.ranking import rank_wines

TOO_MANY_MATCHES_HARD_LIMIT = 250
TOO_MANY_MATCHES_SOFT_LIMIT = 100


def _clean_scalar(value: Any) -> Any:
    """
    Convert pandas missing values into None so JSON output is clean.
    """
    if pd.isna(value):
        return None
    return value


def _normalize_wine_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize dataframe/source-style field names into the frontend API shape.
    """
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
    """
    Convert a DataFrame into JSON-friendly records for the API.
    """
    cleaned_df = df.where(pd.notnull(df), None)
    raw_records = cleaned_df.to_dict(orient="records")
    return [_normalize_wine_record(record) for record in raw_records]


def _should_require_refinement(query: StructuredWineQuery, total_matches: int) -> bool:
    """
    Decide whether the UI should encourage refinement.

    Phase 3 behavior:
    - refinement no longer hides results
    - it only adds a signal that the query is broad
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


def _build_unresolved_entities_message(query: StructuredWineQuery) -> str:
    """
    Build a grounded message for explicit user-provided entities that could
    not be matched to the dataset.
    """
    unresolved_entities = query.unresolved_entities

    if not unresolved_entities:
        return "I could not match one or more requested entities in the current dataset."

    first_entity = unresolved_entities[0]
    value = first_entity.value
    field = first_entity.field
    reason = first_entity.reason

    if reason == UnresolvedReason.FIELD_MISSING_FROM_DATASET:
        return f"The current dataset does not include {value} information."

    if field == "country_or_region":
        return f"I could not find wines from {value} in the current dataset."

    if field == "producer":
        return f"I could not find a producer named {value} in the current dataset."

    if field == "varietal":
        return f"I could not find wines with varietal {value} in the current dataset."

    if field == "name":
        return f"I could not find a wine named {value} in the current dataset."

    return f"I could not match '{value}' in the current dataset."


def _get_effective_page_size(query: StructuredWineQuery) -> int:
    """
    Determine the effective page size for retrieval.

    Priority:
    1. explicit page_size
    2. old limit field for backward compatibility
    """
    if query.page_size and query.page_size > 0:
        return query.page_size

    if query.limit and query.limit > 0:
        return min(query.limit, 20)

    return 10


def _paginate_df(df: pd.DataFrame, page: int, page_size: int) -> tuple[pd.DataFrame, int, int, bool, bool]:
    """
    Slice a ranked dataframe into one page and return paging metadata.
    """
    total_matches = len(df)

    if total_matches == 0:
        empty_df = df.head(0).reset_index(drop=True)
        return empty_df, 1, 0, False, False

    total_pages = math.ceil(total_matches / page_size)
    safe_page = min(max(page, 1), total_pages)

    start_index = (safe_page - 1) * page_size
    end_index = start_index + page_size

    page_df = df.iloc[start_index:end_index].reset_index(drop=True)

    has_prev_page = safe_page > 1
    has_next_page = safe_page < total_pages

    return page_df, safe_page, total_pages, has_prev_page, has_next_page


def retrieve_wines(df: pd.DataFrame, query: StructuredWineQuery) -> dict[str, Any]:
    """
    Run the retrieval pipeline.

    Order of short-circuits:
    1. unsupported request
    2. clarification needed
    3. unresolved explicit entities
    4. normal filtering / ranking / pagination
    """
    page_size = _get_effective_page_size(query)
    requested_page = query.page if query.page > 0 else 1

    if query.intent == QueryIntent.UNSUPPORTED_REQUEST:
        return {
            "query": query.model_dump(),
            "total_matches": 0,
            "returned_count": 0,
            "wines": [],
            "page": 1,
            "page_size": page_size,
            "total_pages": 0,
            "has_next_page": False,
            "has_prev_page": False,
            "message": query.unsupported_reason or "This request is not supported by the dataset.",
        }

    if query.needs_clarification:
        return {
            "query": query.model_dump(),
            "total_matches": 0,
            "returned_count": 0,
            "wines": [],
            "page": 1,
            "page_size": page_size,
            "total_pages": 0,
            "has_next_page": False,
            "has_prev_page": False,
            "message": query.clarification_message or "More detail is needed to search the collection.",
        }

    if query.unresolved_entities:
        return {
            "query": query.model_dump(),
            "total_matches": 0,
            "returned_count": 0,
            "wines": [],
            "page": 1,
            "page_size": page_size,
            "total_pages": 0,
            "has_next_page": False,
            "has_prev_page": False,
            "message": _build_unresolved_entities_message(query),
            "has_unresolved_entities": True,
        }

    filtered_df = retrieve_filtered_wines(df=df, query=query)
    total_matches = len(filtered_df)

    ranked_df = rank_wines(df=filtered_df, query=query)

    paged_df, safe_page, total_pages, has_prev_page, has_next_page = _paginate_df(
        ranked_df,
        requested_page,
        page_size,
    )

    needs_refinement = _should_require_refinement(query, total_matches)

    return {
        "query": query.model_dump(),
        "total_matches": total_matches,
        "returned_count": len(paged_df),
        "wines": _to_records(paged_df),
        "page": safe_page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next_page": has_next_page,
        "has_prev_page": has_prev_page,
        "needs_refinement": needs_refinement,
        "message": None if total_matches > 0 else "No wines matched the requested filters.",
    }
