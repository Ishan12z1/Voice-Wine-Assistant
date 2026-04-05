from __future__ import annotations

import csv
import time

from backend.core.dataset_metadata import (
    field_exists,
    get_canonical_column,
    get_closest_field_values,
    get_dataset_metadata,
    get_field_values,
    get_numeric_range,
    get_top_field_values,
    resolve_field_value,
)


def test_metadata_matches_processed_dataset_columns(production_df, processed_dataset_path) -> None:
    metadata = get_dataset_metadata(processed_dataset_path)

    assert set(production_df.columns).issubset(set(metadata.available_columns))
    assert metadata.canonical_columns["country"] == "country"
    assert metadata.canonical_columns["producer"] == "producer"
    assert metadata.canonical_columns["color"] == "color"


def test_metadata_field_values_are_grounded_to_dataset(processed_dataset_path) -> None:
    country_values = get_field_values("country", processed_dataset_path)
    varietal_values = get_field_values("varietal", processed_dataset_path)
    color_values = get_field_values("color", processed_dataset_path)

    assert "France" in country_values
    assert "Cabernet Sauvignon" in varietal_values
    assert "red" in color_values


def test_metadata_resolution_and_closest_match_support(processed_dataset_path) -> None:
    resolved_country, score, _ = resolve_field_value("country", "show me wines from France", processed_dataset_path)
    assert resolved_country == "France"
    assert score is not None

    resolved_color, color_score, _ = resolve_field_value("color", "best red wines", processed_dataset_path)
    assert resolved_color == "red"
    assert color_score is not None

    closest = get_closest_field_values("country", "Frnace", limit=3, dataset_path=processed_dataset_path)
    assert len(closest) > 0


def test_metadata_numeric_ranges_exist_for_key_numeric_fields(processed_dataset_path) -> None:
    for field_name in ["price", "abv", "best_score", "avg_score", "rating_count"]:
        range_meta = get_numeric_range(field_name, processed_dataset_path)
        assert range_meta is not None
        assert range_meta.canonical_column is not None
        assert range_meta.min_value is not None
        assert range_meta.max_value is not None
        assert range_meta.min_value <= range_meta.max_value


def test_metadata_refreshes_when_dataset_changes(tmp_path) -> None:
    dataset_path = tmp_path / "mini_wines.csv"
    headers = ["name", "producer", "country", "region", "appellation", "varietal", "color", "price"]

    with dataset_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(["Wine A", "Producer A", "France", "Bordeaux", "", "Merlot", "red", "10"])

    metadata_one = get_dataset_metadata(str(dataset_path))
    assert "France" in metadata_one.field_indexes["country"].values

    time.sleep(1.1)

    with dataset_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(["Wine B", "Producer B", "Italy", "Tuscany", "", "Sangiovese", "red", "20"])

    metadata_two = get_dataset_metadata(str(dataset_path))
    assert "France" not in metadata_two.field_indexes["country"].values
    assert "Italy" in metadata_two.field_indexes["country"].values
    assert metadata_two.dataset_mtime > metadata_one.dataset_mtime


def test_metadata_helper_contracts_are_complete(processed_dataset_path) -> None:
    assert field_exists("country", processed_dataset_path) is True
    assert field_exists("nonexistent_field", processed_dataset_path) is False
    assert get_canonical_column("country", processed_dataset_path) == "country"
    assert len(get_top_field_values("varietal", limit=5, dataset_path=processed_dataset_path)) <= 5
