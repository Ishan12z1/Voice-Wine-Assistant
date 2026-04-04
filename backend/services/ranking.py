"""
ranking.py

This file ranks wines after filtering. It does not decide which wines match the
query; it only decides the order in which matching wines should be shown.

"""

from __future__ import annotations

import pandas as pd

from backend.core.schemas import QueryIntent, SortBy, StructuredWineQuery


def _ensure_ranking_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure ranking-related columns exist, even during partial development.

    Step 2 should ideally produce:
    - best_score
    - avg_score
    - rating_count

    This guard makes the app safer while you build incrementally.
    """
    result = df.copy()

    if "best_score" not in result.columns:
        result["best_score"] = pd.NA

    if "avg_score" not in result.columns:
        result["avg_score"] = pd.NA

    if "rating_count" not in result.columns:
        result["rating_count"] = 0

    for col in ["Retail", "best_score", "avg_score", "rating_count", "Vintage", "ABV"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    return result


def _add_value_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a simple value-oriented ranking score.

    Why this exists:
    - Gift and recommendation-style queries should not always return the absolute
      cheapest bottle.
    - We want to reward quality while still considering price.

    This is intentionally simple and explainable.
    """
    result = df.copy()

    avg_score = result["avg_score"].fillna(result["best_score"]).fillna(0)
    rating_count = result["rating_count"].fillna(0)
    price = result["Retail"].fillna(9999)

    # Small bonus for having more ratings, capped so it does not dominate.
    review_bonus = rating_count.clip(lower=0, upper=50) * 0.05

    # Penalize high price for value-oriented use cases.
    price_penalty = price * 0.08

    result["value_score"] = avg_score + review_bonus - price_penalty
    return result


def rank_wines(df: pd.DataFrame, query: StructuredWineQuery) -> pd.DataFrame:
    """
    Rank already-filtered wines according to query.sort_by.

    The schema already fills reasonable sort defaults based on intent, so this
    function mainly executes that policy cleanly.
    """
    result = _ensure_ranking_columns(df)
    result = _add_value_score(result)

    sort_by = query.sort_by
    intent = query.intent

    if sort_by == SortBy.PRICE_ASC:
        return result.sort_values(
            by=["Retail", "best_score", "avg_score"],
            ascending=[True, False, False],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.PRICE_DESC:
        return result.sort_values(
            by=["Retail", "best_score", "avg_score"],
            ascending=[False, False, False],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.BEST_SCORE_DESC:
        return result.sort_values(
            by=["best_score", "avg_score", "Retail"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.AVG_SCORE_DESC:
        return result.sort_values(
            by=["avg_score", "best_score", "Retail"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.VALUE_DESC:
        return result.sort_values(
            by=["value_score", "avg_score", "best_score", "Retail"],
            ascending=[False, False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.NAME_ASC:
        return result.sort_values(
            by=["Name", "best_score"],
            ascending=[True, False],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.VINTAGE_DESC:
        return result.sort_values(
            by=["Vintage", "best_score", "Retail"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if sort_by == SortBy.RELEVANCE:
        # Your schema uses RELEVANCE as the default generic browse mode.
        # Since you do not yet have semantic retrieval, we need a deterministic
        # fallback definition for "relevance".
        #
        # For now:
        # - browsing queries favor stronger wines first
        # - then cheaper bottles break ties
        return result.sort_values(
            by=["avg_score", "best_score", "Retail"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    # Fallback by intent if somehow sort_by was not enough.
    if intent == QueryIntent.BEST_RATED_UNDER_BUDGET:
        return result.sort_values(
            by=["best_score", "avg_score", "Retail"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    if intent == QueryIntent.CHEAPEST:
        return result.sort_values(
            by=["Retail", "best_score"],
            ascending=[True, False],
            na_position="last",
        ).reset_index(drop=True)

    if intent == QueryIntent.MOST_EXPENSIVE:
        return result.sort_values(
            by=["Retail", "best_score"],
            ascending=[False, False],
            na_position="last",
        ).reset_index(drop=True)

    if intent == QueryIntent.GIFT_RECOMMENDATION:
        return result.sort_values(
            by=["value_score", "best_score", "Retail"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    return result.sort_values(
        by=["avg_score", "best_score", "Retail"],
        ascending=[False, False, True],
        na_position="last",
    ).reset_index(drop=True)