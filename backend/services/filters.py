"""
filters.py

This file applies the structured filters from StructuredWineQuery to the wine
dataset. It is responsible only for narrowing the dataset down to matching rows.

"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backend.core.schemas import QueryFilters, StructuredWineQuery


def _safe_contains(series: pd.Series, value: Optional[str]) -> pd.Series:
    """
    Perform a case-insensitive substring match.

    We use substring matching because user requests may be broader than the exact
    dataset text. For example, 'cabernet' should match 'Cabernet Sauvignon'.
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

    Every active filter must match for a wine to remain in the result set.
    """
    result = df.copy()

    # Text / categorical filters
    result = _apply_text_filter(result, "Name", filters.name)
    result = _apply_text_filter(result, "Producer", filters.producer)
    result = _apply_text_filter(result, "Country", filters.country)
    result = _apply_text_filter(result, "Region", filters.region)
    result = _apply_text_filter(result, "Appellation", filters.appellation)
    result = _apply_text_filter(result, "Varietal", filters.varietal)

    # Color is stored as a lowercase text field in the dataset.
    if filters.color is not None:
        result = _apply_text_filter(result, "color", str(filters.color))

    # Numeric filters
    result = _apply_min_filter(result, "Retail", filters.min_price)
    result = _apply_max_filter(result, "Retail", filters.max_price)

    result = _apply_min_filter(result, "Vintage", filters.min_vintage)
    result = _apply_max_filter(result, "Vintage", filters.max_vintage)

    result = _apply_min_filter(result, "ABV", filters.min_abv)
    result = _apply_max_filter(result, "ABV", filters.max_abv)

    if filters.volume_ml is not None and "volume_ml" in result.columns:
        volume_col = pd.to_numeric(result["volume_ml"], errors="coerce")
        result = result[volume_col == filters.volume_ml]

    # Quality filters from Step 2 derived columns
    result = _apply_min_filter(result, "best_score", filters.min_best_score)
    result = _apply_min_filter(result, "avg_score", filters.min_avg_score)
    result = _apply_min_filter(result, "rating_count", filters.min_rating_count)

    # Optional data-quality-aware flags
    if filters.require_varietal:
        if "Varietal" in result.columns:
            result = result[result["Varietal"].notna() & (result["Varietal"].astype(str).str.strip() != "")]

    if filters.require_vintage:
        if "Vintage" in result.columns:
            vintage_col = pd.to_numeric(result["Vintage"], errors="coerce")
            result = result[vintage_col.notna()]

    return result.reset_index(drop=True)


def retrieve_filtered_wines(df: pd.DataFrame, query: StructuredWineQuery) -> pd.DataFrame:
    """
    Convenience wrapper that takes the full structured query and returns only the
    rows that match its filters.
    """
    return apply_filters(df=df, filters=query.filters)