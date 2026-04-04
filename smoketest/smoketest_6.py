"""
smoke_test_step6.py

This file runs an end-to-end smoke test for Step 6. It loads the dataset,
creates several StructuredWineQuery examples, runs Step 5 retrieval, then
passes the retrieval output into Step 6 response generation.

Why this file exists:
- It verifies that Step 6 is wired correctly on top of Step 5.
- It checks that summaries and response metadata are produced cleanly.
- It catches obvious integration problems before API wiring in Step 7.
"""

from __future__ import annotations

import pandas as pd

from backend.core.schemas import (
    QueryFilters,
    QueryIntent,
    StructuredWineQuery,
    WineColor,
)
from backend.services.retrieval import retrieve_wines
from backend.services.responder import build_response


DATA_PATH = "data//raw//Assignment wine dataset - Sheet1.csv"


def load_dataset(path: str) -> pd.DataFrame:
    """
    Load the dataset for smoke testing.

    Adjust the path if your CSV lives elsewhere.
    """
    df = pd.read_csv(path)

    # Convert likely numeric columns safely.
    for col in ["Retail", "Vintage", "ABV", "volume_ml", "best_score", "avg_score", "rating_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def print_response_preview(label: str, response: dict) -> None:
    """
    Print a compact preview of the Step 6 response payload.
    """
    print(f"\n=== {label} ===")
    print(f"response_type: {response.get('response_type')}")
    print(f"total_matches: {response.get('total_matches')}")
    print(f"returned_count: {response.get('returned_count')}")
    print(f"show_results: {response.get('show_results')}")
    print(f"summary: {response.get('summary')}")
    print(f"spoken_summary: {response.get('spoken_summary')}")
    print(f"applied_filters_text: {response.get('applied_filters_text')}")
    print(f"ranking_basis_text: {response.get('ranking_basis_text')}")


def test_results_response(df: pd.DataFrame) -> None:
    """
    Smoke test:
    - normal result case
    - response_type should be 'results'
    - summary fields should be present
    """
    query = StructuredWineQuery(
        original_question="Best-rated red wines under $50",
        intent=QueryIntent.BEST_RATED_UNDER_BUDGET,
        filters=QueryFilters(
            color=WineColor.RED,
            max_price=50,
        ),
        limit=5,
    )

    retrieval_result = retrieve_wines(df, query)
    response = build_response(query, retrieval_result)

    assert response["response_type"] == "results"
    assert response["total_matches"] >= 0
    assert response["returned_count"] <= 5
    assert isinstance(response["summary"], str) and response["summary"].strip()
    assert isinstance(response["spoken_summary"], str) and response["spoken_summary"].strip()
    assert isinstance(response["applied_filters_text"], str)
    assert isinstance(response["ranking_basis_text"], str)
    assert response["show_results"] is True

    print_response_preview("results response", response)


def test_no_results_response(df: pd.DataFrame) -> None:
    """
    Smoke test:
    - no-results case
    - response_type should be 'no_results'
    - show_results should be False
    """
    query = StructuredWineQuery(
        original_question="Show me red wines from Mars under $2",
        intent=QueryIntent.BROWSE_COLLECTION,
        filters=QueryFilters(
            country="Mars",
            color=WineColor.RED,
            max_price=2,
        ),
        limit=5,
    )

    retrieval_result = retrieve_wines(df, query)
    response = build_response(query, retrieval_result)

    assert response["total_matches"] == 0
    assert response["returned_count"] == 0
    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert isinstance(response["summary"], str) and response["summary"].strip()
    assert isinstance(response["spoken_summary"], str) and response["spoken_summary"].strip()

    print_response_preview("no results response", response)


def test_clarification_response(df: pd.DataFrame) -> None:
    """
    Smoke test:
    - ambiguous request case
    - response_type should be 'clarification'
    """
    query = StructuredWineQuery(
        original_question="Recommend something nice",
        intent=QueryIntent.AMBIGUOUS_REQUEST,
        needs_clarification=True,
        clarification_message="Please specify a budget, color, varietal, or occasion.",
    )

    retrieval_result = retrieve_wines(df, query)
    response = build_response(query, retrieval_result)

    assert response["response_type"] == "clarification"
    assert response["show_results"] is False
    assert response["returned_count"] == 0
    assert response["total_matches"] == 0
    assert "Please specify" in response["summary"]

    print_response_preview("clarification response", response)


def test_unsupported_response(df: pd.DataFrame) -> None:
    """
    Smoke test:
    - unsupported request case
    - response_type should be 'unsupported'
    """
    query = StructuredWineQuery(
        original_question="Which wine pairs best with sushi and jasmine aromas?",
        intent=QueryIntent.UNSUPPORTED_REQUEST,
        unsupported_reason="Food pairing and aroma analysis are not supported in this version.",
    )

    retrieval_result = retrieve_wines(df, query)
    response = build_response(query, retrieval_result)

    assert response["response_type"] == "unsupported"
    assert response["show_results"] is False
    assert response["returned_count"] == 0
    assert response["total_matches"] == 0
    assert "not supported" in response["summary"].lower()

    print_response_preview("unsupported response", response)


def main() -> None:
    """
    Run all Step 6 smoke tests.
    """
    df = load_dataset(DATA_PATH)

    print("Loaded dataset")
    print(f"rows={len(df)}, cols={len(df.columns)}")

    test_results_response(df)
    test_no_results_response(df)
    test_clarification_response(df)
    test_unsupported_response(df)

    print("\nAll Step 6 smoke tests passed.")


if __name__ == "__main__":
    main()