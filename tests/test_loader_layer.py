from __future__ import annotations

import pandas as pd

from backend.services.loader import (
    RAW_TO_CANONICAL_COLUMNS,
    build_clean_wines,
    build_enriched_wines,
    normalize_color,
    normalize_varietal,
    parse_ratings_blob,
)


def test_raw_loader_keeps_expected_columns(raw_df) -> None:
    expected_columns = {value for value in RAW_TO_CANONICAL_COLUMNS.values()}
    assert expected_columns.issubset(set(raw_df.columns))


def test_clean_builder_normalizes_edge_case_values() -> None:
    raw_like = pd.DataFrame(
        [
            {
                "wine_id": 1,
                "name": "  TEST WINE  ",
                "producer": "  Example Producer ",
                "country": "FRANCE",
                "region": "BORDEAUX",
                "appellation": "MARGAUX",
                "varietal": "Rose Blend",
                "color": "ros\u00c3\u00a9",
                "vintage": "2019",
                "price": "$19.50",
                "abv": "13.5",
                "volume_ml": "750",
                "upc": "12345",
                "image_url": " https://example.com/wine.jpg ",
                "reference_url": " https://example.com/product ",
                "professional_ratings_raw": '[{"source": "Critic", "score": 91, "max_score": 100}]',
            }
        ]
    )

    clean_df = build_clean_wines(raw_like)
    row = clean_df.iloc[0]

    assert row["name"] == "TEST WINE"
    assert row["producer"] == "Example Producer"
    assert row["country"] == "France"
    assert row["region"] == "Bordeaux"
    assert row["appellation"] == "Margaux"
    assert row["varietal"] == "Ros\u00e9 Blend"
    assert row["color"] == "rose"
    assert row["price"] == 19.5
    assert row["abv"] == 13.5
    assert row["volume_ml"] == 750


def test_enriched_builder_adds_rating_stats_and_search_text(clean_df) -> None:
    enriched = build_enriched_wines(clean_df)

    for column in ["best_score", "avg_score", "rating_count", "has_varietal", "has_vintage", "search_text"]:
        assert column in enriched.columns

    assert enriched["search_text"].notna().any()
    assert (enriched["rating_count"] >= 0).all()


def test_parse_ratings_blob_handles_invalid_input() -> None:
    assert parse_ratings_blob(None) == []
    assert parse_ratings_blob("") == []
    assert parse_ratings_blob("not-json") == []


def test_normalize_helpers_cover_known_dataset_edge_cases() -> None:
    assert normalize_color("ros\u00c3\u00a9") == "rose"
    assert normalize_color("ros\u00e9") == "rose"
    assert normalize_color("Sparkling") == "sparkling"
    assert normalize_varietal("Rose Blend") == "Ros\u00e9 Blend"
