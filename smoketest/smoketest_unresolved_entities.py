from __future__ import annotations

import pandas as pd

from backend.core.data_loader import DEFAULT_DATASET_PATH, load_wine_dataset
from backend.services.pipeline import run_query_pipeline
from backend.services.parser.parser import parse_query


def test_parse_query_tracks_unresolved_location() -> None:
    """
    The parser should preserve an explicit unmatched location instead of
    silently dropping it.
    """
    query = parse_query("best red wine in India")

    assert query.filters.color == "red" or str(query.filters.color) == "WineColor.RED"
    assert query.filters.country is None
    assert query.filters.region is None
    assert query.filters.appellation is None

    assert len(query.unresolved_entities) == 1
    assert query.unresolved_entities[0].field == "country_or_region"
    assert query.unresolved_entities[0].value == "India"


def test_valid_country_still_returns_results(df: pd.DataFrame) -> None:
    """
    A valid explicit country phrase should still work normally.
    """
    response = run_query_pipeline("best red wine from France", df, limit_override=5)

    assert response["response_type"] == "results"
    assert response["show_results"] is True
    assert response["query"]["filters"]["country"] == "France"
    assert response["query"]["filters"]["region"] is None
    assert response["returned_count"] > 0
    assert response["total_matches"] > 0


def test_invalid_location_returns_grounded_no_results(df: pd.DataFrame) -> None:
    """
    An explicit location not present in the dataset should produce grounded
    no-results instead of unrelated wines.
    """
    response = run_query_pipeline("best red wine in India", df, limit_override=5)

    assert response["response_type"] == "no_results"
    assert response["show_results"] is False
    assert response["returned_count"] == 0
    assert response["total_matches"] == 0
    assert response["query"]["unresolved_entities"][0]["value"] == "India"
    assert "India" in response["summary"]
    assert "current dataset" in response["summary"]


def test_producer_phrase_is_not_falsely_treated_as_location(df: pd.DataFrame) -> None:
    """
    A phrase after 'from' can still be a producer. That must not become an
    unresolved country/region.
    """
    response = run_query_pipeline(
        "Find wines from Stag's Leap Wine Cellars under $100",
        df,
        limit_override=5,
    )

    assert response["response_type"] == "results"
    assert response["show_results"] is True
    assert response["query"]["filters"]["producer"] == "Stag's Leap Wine Cellars"
    assert response["query"]["unresolved_entities"] == []
    assert response["returned_count"] > 0


def test_invalid_location_does_not_return_generic_filtered_results(df: pd.DataFrame) -> None:
    """
    This is the key regression guard:
    'best red wine in India' must not fall back to generic red wine results.
    """
    response = run_query_pipeline("best red wine in India", df, limit_override=5)

    assert response["wines"] == []
    assert response["show_results"] is False
    assert response["query"]["filters"]["color"] == "red"


def main() -> None:
    """
    Run all unresolved-entity smoke tests.
    """
    df = load_wine_dataset(DEFAULT_DATASET_PATH)

    test_parse_query_tracks_unresolved_location()
    test_valid_country_still_returns_results(df)
    test_invalid_location_returns_grounded_no_results(df)
    test_producer_phrase_is_not_falsely_treated_as_location(df)
    test_invalid_location_does_not_return_generic_filtered_results(df)

    print("All unresolved-entity smoke tests passed.")


if __name__ == "__main__":
    main()