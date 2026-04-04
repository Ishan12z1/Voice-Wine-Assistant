"""
ranking.py

This file ranks wines after filtering, using the canonical Step 2
enriched dataset columns.
"""

from __future__ import annotations

import pandas as pd

from backend.core.schemas import QueryIntent, SortBy, StructuredWineQuery


def _ensure_ranking_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure ranking-related columns exist and are numeric where needed.
    """
    result = df.copy()

    if "best_score" not in result.columns:
        result["best_score"] = pd.NA

    if "avg_score" not in result.columns:
        result["avg_score"] = pd.NA

    if "rating_count" not in result.columns:
        result["rating_count"] = 0

    for col in ["price", "best_score", "avg_score", "rating_count", "vintage", "abv"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    return result


def _add_value_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a simple value score that rewards quality while penalizing price.
    """
    result = df.copy()

    avg_score = result["avg_score"].fillna(result["best_score"]).fillna(0)
    rating_count = result["rating_count"].fillna(0)
    price = result["price"].fillna(9999)

    review_bonus = rating_count.clip(lower=0, upper=50) * 0.05
    price_penalty = price * 0.08

    result["value_score"] = avg_score + review_bonus - price_penalty
    return result


def rank_wines(df: pd.DataFrame, query: StructuredWineQuery) -> pd.DataFrame:
    """
    Rank wines according to query.sort_by.
    """
    result = _ensure_ranking_columns(df)
    result = _add_value_score(result)

    sort_by = query.sort_by
    intent = query.intent

    if sort_by == SortBy.PRICE_ASC:
        return result.sort_values(
            by=["price", "best_score", "avg_score"],
            ascending=[True, False, False],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.PRICE_DESC:
        return result.sort_values(
            by=["price", "best_score", "avg_score"],
            ascending=[False, False, False],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.BEST_SCORE_DESC:
        return result.sort_values(
            by=["best_score", "avg_score", "price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.AVG_SCORE_DESC:
        return result.sort_values(
            by=["avg_score", "best_score", "price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.VALUE_DESC:
        return result.sort_values(
            by=["value_score", "avg_score", "best_score", "price"],
            ascending=[False, False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.NAME_ASC:
        return result.sort_values(
            by=["name", "best_score"],
            ascending=[True, False],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.VINTAGE_DESC:
        return result.sort_values(
            by=["vintage", "best_score", "price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.RELEVANCE:
        return result.sort_values(
            by=["avg_score", "best_score", "price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if intent == QueryIntent.BEST_RATED_UNDER_BUDGET:
        return result.sort_values(
            by=["best_score", "avg_score", "price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if intent == QueryIntent.CHEAPEST:
        return result.sort_values(
            by=["price", "best_score"],
            ascending=[True, False],
            na_position="last",
        ).reset_index(drop=True)

    if intent == QueryIntent.MOST_EXPENSIVE:
        return result.sort_values(
            by=["price", "best_score"],
            ascending=[False, False],
            na_position="last",
        ).reset_index(drop=True)

    if intent == QueryIntent.GIFT_RECOMMENDATION:
        return result.sort_values(
            by=["value_score", "best_score", "price"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    return result.sort_values(
        by=["avg_score", "best_score", "price"],
        ascending=[False, False, True],
        na_position="last",
    ).reset_index(drop=True)