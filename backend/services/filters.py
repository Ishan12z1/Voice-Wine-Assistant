"""
filters.py

This file applies the structured filters from StructuredWineQuery to the
canonical enriched wine dataset produced in Step 2.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backend.core.schemas import QueryFilters, StructuredWineQuery


def _safe_contains(series: pd.Series, value: Optional[str]) -> pd.Series:
    """
    Perform a case-insensitive substring match.
    """
    if not value:
        return pd.Series(True, index=series.index)

    return (
        series.fillna("")
        .astype(str)
        .str.lower()
        .str.contains(value.strip().lower(), regex=False)
    )


def _apply_text_filter(df: pd.DataFrame, column: str, value: Optional[str]) -> pd.DataFrame:
    """
    Apply a text filter to a DataFrame column if both the column and value exist.
    """
    if not value or column not in df.columns:
        return df

    return df[_safe_contains(df[column], value)]


def _apply_min_filter(df: pd.DataFrame, column: str, value: Optional[float]) -> pd.DataFrame:
    """
    Keep rows where the numeric column is >= value.
    """
    if value is None or column not in df.columns:
        return df

    numeric_col = pd.to_numeric(df[column], errors="coerce")
    return df[numeric_col >= value]


def _apply_max_filter(df: pd.DataFrame, column: str, value: Optional[float]) -> pd.DataFrame:
    """
    Keep rows where the numeric column is <= value.
    """
    if value is None or column not in df.columns:
        return df

    numeric_col = pd.to_numeric(df[column], errors="coerce")
    return df[numeric_col <= value]


def apply_filters(df: pd.DataFrame, filters: QueryFilters) -> pd.DataFrame:
    """
    Apply all supported structured filters with AND logic.
    """
    result = df.copy()

    # Canonical text fields from Step 2
    result = _apply_text_filter(result, "name", filters.name)
    result = _apply_text_filter(result, "producer", filters.producer)
    result = _apply_text_filter(result, "country", filters.country)
    result = _apply_text_filter(result, "region", filters.region)
    result = _apply_text_filter(result, "appellation", filters.appellation)
    result = _apply_text_filter(result, "varietal", filters.varietal)

    if filters.color is not None:
        result = _apply_text_filter(result, "color", filters.color.value)

    # Canonical numeric fields from Step 2
    result = _apply_min_filter(result, "price", filters.min_price)
    result = _apply_max_filter(result, "price", filters.max_price)

    result = _apply_min_filter(result, "vintage", filters.min_vintage)
    result = _apply_max_filter(result, "vintage", filters.max_vintage)

    result = _apply_min_filter(result, "abv", filters.min_abv)
    result = _apply_max_filter(result, "abv", filters.max_abv)

    if filters.volume_ml is not None and "volume_ml" in result.columns:
        volume_col = pd.to_numeric(result["volume_ml"], errors="coerce")
        result = result[volume_col == filters.volume_ml]

    result = _apply_min_filter(result, "best_score", filters.min_best_score)
    result = _apply_min_filter(result, "avg_score", filters.min_avg_score)
    result = _apply_min_filter(result, "rating_count", filters.min_rating_count)

    if filters.require_varietal and "varietal" in result.columns:
        result = result[result["varietal"].notna() & (result["varietal"].astype(str).str.strip() != "")]

    if filters.require_vintage and "vintage" in result.columns:
        vintage_col = pd.to_numeric(result["vintage"], errors="coerce")
        result = result[vintage_col.notna()]

    return result.reset_index(drop=True)


def retrieve_filtered_wines(df: pd.DataFrame, query: StructuredWineQuery) -> pd.DataFrame:
    """
    Filter the canonical enriched dataset using query.filters.
    """
    return apply_filters(df=df, filters=query.filters)