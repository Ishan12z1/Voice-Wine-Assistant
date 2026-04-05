from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.data_loader import load_wine_dataset
from backend.core.settings import get_configured_dataset_path
from backend.core.dataset_metadata import get_closest_field_values, resolve_field_value
from backend.services.pipeline import run_query_pipeline


def _load_df():
    return load_wine_dataset(get_configured_dataset_path())


def test_metadata_helpers_ground_against_current_dataset() -> None:
    resolved_country, score, _ = resolve_field_value("country", "show me wines from France")
    assert resolved_country == "France"
    assert score is not None

    resolved_color, color_score, _ = resolve_field_value("color", "best red wines")
    assert resolved_color == "red"
    assert color_score is not None

    closest = get_closest_field_values("country", "Frnace", limit=3)
    assert len(closest) > 0


def test_broad_query_returns_results_with_backend_refinement_suggestions() -> None:
    df = _load_df()
    response = run_query_pipeline("show me wines", df, page_override=1, page_size_override=5)

    assert response["response_type"] == "results"
    assert response["show_results"] is True
    assert response["needs_refinement"] is True
    assert response["returned_count"] > 0
    assert len(response["followup_suggestions"]) > 0


def test_invalid_location_returns_grounded_no_results_with_suggestions() -> None:
    df = _load_df()
    response = run_query_pipeline("best red wine in India", df, limit_override=5)

    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert response["query"]["unresolved_entities"][0]["field"] == "country_or_region"
    assert response["query"]["unresolved_entities"][0]["reason"] == "not_in_dataset"
    assert "India" in response["summary"]
    assert len(response["followup_suggestions"]) > 0


def test_missing_dataset_capability_is_reported_explicitly() -> None:
    df = _load_df()
    response = run_query_pipeline("show me dry red wines", df, limit_override=5)

    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert response["query"]["unresolved_entities"][0]["field"] == "sweetness"
    assert response["query"]["unresolved_entities"][0]["reason"] == "field_missing_from_dataset"
    assert "does not include sweetness information" in response["summary"].lower()
    assert len(response["followup_suggestions"]) > 0


def test_invalid_varietal_does_not_silently_disappear() -> None:
    df = _load_df()
    response = run_query_pipeline(
        "show me wines by grape Mystery Grape under $30",
        df,
        limit_override=5,
    )

    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert response["query"]["unresolved_entities"][0]["field"] == "varietal"
    assert response["query"]["unresolved_entities"][0]["reason"] == "not_in_dataset"
    assert len(response["followup_suggestions"]) > 0


def test_clarification_flows_return_backend_driven_suggestions() -> None:
    df = _load_df()
    response = run_query_pipeline("Recommend a housewarming gift", df, limit_override=5)

    assert response["response_type"] == "clarification"
    assert response["show_results"] is False
    assert response["query"]["missing_fields"] == ["budget"]
    assert len(response["followup_suggestions"]) > 0


def main() -> None:
    test_metadata_helpers_ground_against_current_dataset()
    test_broad_query_returns_results_with_backend_refinement_suggestions()
    test_invalid_location_returns_grounded_no_results_with_suggestions()
    test_missing_dataset_capability_is_reported_explicitly()
    test_invalid_varietal_does_not_silently_disappear()
    test_clarification_flows_return_backend_driven_suggestions()
    print("All grounded query logic tests passed.")


if __name__ == "__main__":
    main()
