from __future__ import annotations

from backend.services.pipeline import run_query_pipeline


def test_pipeline_returns_page_one_results_for_broad_query(production_df) -> None:
    response = run_query_pipeline("show me wines", production_df, page_override=1, page_size_override=5)

    assert response["response_type"] == "results"
    assert response["show_results"] is True
    assert response["needs_refinement"] is True
    assert response["returned_count"] == 5
    assert response["page"] == 1
    assert len(response["followup_suggestions"]) > 0


def test_pipeline_refinement_suggestions_do_not_repeat_active_color(production_df) -> None:
    response = run_query_pipeline("best rated white wine", production_df, page_override=1, page_size_override=5)

    assert response["response_type"] == "results"
    assert response["query"]["filters"]["color"] == "white"
    color_suggestions = [
        suggestion["value"]
        for suggestion in response["followup_suggestions"]
        if suggestion["mode"] == "color"
    ]
    assert "white" not in color_suggestions


def test_pipeline_clamps_page_beyond_end(production_df) -> None:
    response = run_query_pipeline(
        "best red wine from France",
        production_df,
        page_override=999,
        page_size_override=3,
    )

    assert response["response_type"] == "results"
    assert response["page"] == response["total_pages"]
    assert response["has_next_page"] is False


def test_pipeline_invalid_location_does_not_fall_back_to_generic_results(production_df) -> None:
    response = run_query_pipeline("best red wine in India", production_df, limit_override=5)

    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert response["wines"] == []
    assert response["query"]["unresolved_entities"][0]["value"] == "India"
    assert "India" in response["summary"]


def test_pipeline_missing_dataset_capability_returns_grounded_message(production_df) -> None:
    response = run_query_pipeline("show me dry red wines", production_df, limit_override=5)

    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert response["query"]["unresolved_entities"][0]["field"] == "sweetness"
    assert "does not include sweetness information" in response["summary"].lower()


def test_pipeline_returns_backend_suggestions_for_clarification(production_df) -> None:
    response = run_query_pipeline("Recommend a housewarming gift", production_df, limit_override=5)

    assert response["response_type"] == "clarification"
    assert response["show_results"] is False
    assert response["query"]["missing_fields"] == ["budget"]
    assert len(response["followup_suggestions"]) > 0


def test_pipeline_orders_cheapest_query_ascending_by_price(production_df) -> None:
    response = run_query_pipeline("show me cheapest red wines", production_df, page_override=1, page_size_override=5)

    assert response["response_type"] == "results"
    prices = [wine["price"] for wine in response["wines"] if wine["price"] is not None]
    assert prices == sorted(prices)
