from __future__ import annotations

from backend.services.pipeline import run_query_pipeline


def test_real_dataset_country_query_returns_consistent_filters(production_df) -> None:
    response = run_query_pipeline("best red wine from France", production_df, page_override=1, page_size_override=5)

    assert response["response_type"] == "results"
    assert response["query"]["filters"]["country"] == "France"
    assert response["query"]["filters"]["color"] == "red"
    assert response["returned_count"] > 0


def test_real_dataset_producer_query_returns_grounded_producer(production_df) -> None:
    response = run_query_pipeline(
        "Find wines from Stag's Leap Wine Cellars under $100",
        production_df,
        page_override=1,
        page_size_override=5,
    )

    assert response["response_type"] == "results"
    assert response["query"]["filters"]["producer"] == "Stag's Leap Wine Cellars"
    assert response["query"]["unresolved_entities"] == []
    assert response["returned_count"] > 0


def test_real_dataset_invalid_varietal_is_grounded_not_ignored(production_df) -> None:
    response = run_query_pipeline(
        "show me wines by grape Mystery Grape under $30",
        production_df,
        limit_override=5,
    )

    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert response["query"]["unresolved_entities"][0]["field"] == "varietal"
    assert response["query"]["unresolved_entities"][0]["reason"] == "not_in_dataset"
    assert len(response["followup_suggestions"]) > 0


def test_real_dataset_query_page_boundaries_stay_consistent(production_df) -> None:
    first_page = run_query_pipeline("show me wines", production_df, page_override=1, page_size_override=3)
    second_page = run_query_pipeline("show me wines", production_df, page_override=2, page_size_override=3)

    assert first_page["response_type"] == "results"
    assert second_page["response_type"] == "results"
    assert first_page["page"] == 1
    assert second_page["page"] == 2
    assert first_page["wines"] != second_page["wines"]
