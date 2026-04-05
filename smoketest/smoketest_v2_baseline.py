from __future__ import annotations

import pandas as pd

from backend.core.data_loader import DEFAULT_DATASET_PATH, load_wine_dataset
from backend.services.parser.parser import parse_query
from backend.services.retrieval import retrieve_wines
from backend.services.responder import build_response


def run_pipeline(question: str, df: pd.DataFrame, limit: int = 5) -> dict:
    query = parse_query(question)

    if query.limit != limit:
        query = query.model_copy(update={"limit": limit})

    retrieval_result = retrieve_wines(df, query)
    response = build_response(query, retrieval_result)
    return response


def test_best_rated_under_budget(df: pd.DataFrame) -> None:
    response = run_pipeline("Best-rated red wines under $50", df)

    assert response["response_type"] == "results"
    assert response["show_results"] is True
    assert response["returned_count"] == 5
    assert response["total_matches"] > 0
    assert len(response["wines"]) == 5


def test_broad_browse_refinement(df: pd.DataFrame) -> None:
    response = run_pipeline("show me wines", df)

    assert response["response_type"] == "too_many_matches"
    assert response["show_results"] is False
    assert response["returned_count"] == 0
    assert response["total_matches"] > 0


def test_gift_budget_clarification(df: pd.DataFrame) -> None:
    response = run_pipeline("Recommend a housewarming gift", df)

    assert response["response_type"] == "clarification"
    assert response["query"]["missing_fields"] == ["budget"]
    assert response["query"]["occasion"] == "housewarming"
    assert response["show_results"] is False


def test_color_clarification(df: pd.DataFrame) -> None:
    response = run_pipeline("Recommend a wine under $30", df)

    assert response["response_type"] == "clarification"
    assert response["query"]["missing_fields"] == ["color"]
    assert response["query"]["filters"]["max_price"] == 30.0
    assert response["show_results"] is False


def test_varietal_clarification(df: pd.DataFrame) -> None:
    response = run_pipeline("Recommend a wine by grape under $30", df)

    assert response["response_type"] == "clarification"
    assert response["query"]["missing_fields"] == ["varietal"]
    assert response["query"]["filters"]["max_price"] == 30.0
    assert response["query"]["filters"]["require_varietal"] is True
    assert response["show_results"] is False


def test_unsupported_question(df: pd.DataFrame) -> None:
    response = run_pipeline("Teach me how tannins work", df)

    assert response["response_type"] == "unsupported"
    assert response["show_results"] is False
    assert response["returned_count"] == 0


def main() -> None:
    df = load_wine_dataset(DEFAULT_DATASET_PATH)

    test_best_rated_under_budget(df)
    test_broad_browse_refinement(df)
    test_gift_budget_clarification(df)
    test_color_clarification(df)
    test_varietal_clarification(df)
    test_unsupported_question(df)

    print("All V2 baseline smoke tests passed.")


if __name__ == "__main__":
    main()