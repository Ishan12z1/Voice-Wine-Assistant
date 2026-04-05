from __future__ import annotations

from backend.core.data_loader import DEFAULT_DATASET_PATH
from backend.core.dataset_metadata import (
    get_canonical_column,
    get_dataset_metadata,
    get_field_values,
    get_normalized_lookup,
    get_top_field_values,
)


def test_metadata_loads() -> None:
    metadata = get_dataset_metadata(DEFAULT_DATASET_PATH)

    assert metadata.dataset_path
    assert metadata.dataset_mtime > 0
    assert len(metadata.available_columns) > 0
    assert isinstance(metadata.canonical_columns, dict)
    assert isinstance(metadata.field_indexes, dict)
    assert isinstance(metadata.numeric_ranges, dict)


def test_core_text_fields_exist() -> None:
    metadata = get_dataset_metadata(DEFAULT_DATASET_PATH)

    for field_name in ["name", "producer", "country", "region", "appellation", "varietal", "color"]:
        assert field_name in metadata.field_indexes, f"Missing field index for {field_name}"

    # These should usually exist in your processed dataset.
    assert metadata.field_indexes["name"].canonical_column is not None
    assert metadata.field_indexes["producer"].canonical_column is not None
    assert metadata.field_indexes["country"].canonical_column is not None
    assert metadata.field_indexes["region"].canonical_column is not None
    assert metadata.field_indexes["varietal"].canonical_column is not None
    assert metadata.field_indexes["color"].canonical_column is not None


def test_text_field_values_are_non_empty() -> None:
    metadata = get_dataset_metadata(DEFAULT_DATASET_PATH)

    assert len(metadata.field_indexes["name"].values) > 0
    assert len(metadata.field_indexes["producer"].values) > 0
    assert len(metadata.field_indexes["country"].values) > 0
    assert len(metadata.field_indexes["region"].values) > 0
    assert len(metadata.field_indexes["varietal"].values) > 0
    assert len(metadata.field_indexes["color"].values) > 0


def test_normalized_lookups_exist() -> None:
    metadata = get_dataset_metadata(DEFAULT_DATASET_PATH)

    for field_name in ["country", "region", "producer", "varietal", "name"]:
        lookup = metadata.field_indexes[field_name].normalized_to_canonical
        assert isinstance(lookup, dict)
        assert len(lookup) > 0, f"Expected normalized lookup for {field_name} to be non-empty"


def test_top_values_exist() -> None:
    metadata = get_dataset_metadata(DEFAULT_DATASET_PATH)

    for field_name in ["country", "region", "producer", "varietal", "color"]:
        top_values = metadata.field_indexes[field_name].top_values
        assert isinstance(top_values, list)
        assert len(top_values) > 0, f"Expected top values for {field_name} to be non-empty"


def test_numeric_ranges_exist_when_columns_exist() -> None:
    metadata = get_dataset_metadata(DEFAULT_DATASET_PATH)

    for field_name in ["price", "vintage", "abv", "volume_ml", "best_score", "avg_score", "rating_count"]:
        assert field_name in metadata.numeric_ranges, f"Missing numeric range metadata for {field_name}"

        range_meta = metadata.numeric_ranges[field_name]

        # If the dataset contains the column, min/max should be populated for non-empty numeric columns.
        if range_meta.canonical_column is not None:
            assert range_meta.min_value is not None, f"Expected min_value for {field_name}"
            assert range_meta.max_value is not None, f"Expected max_value for {field_name}"
            assert range_meta.min_value <= range_meta.max_value, (
                f"Expected {field_name} min <= max, got {range_meta.min_value} > {range_meta.max_value}"
            )


def test_public_helper_functions() -> None:
    metadata = get_dataset_metadata(DEFAULT_DATASET_PATH)

    country_values = get_field_values("country", DEFAULT_DATASET_PATH)
    assert country_values == metadata.field_indexes["country"].values
    assert len(country_values) > 0

    top_varietals = get_top_field_values("varietal", limit=5, dataset_path=DEFAULT_DATASET_PATH)
    assert len(top_varietals) > 0
    assert len(top_varietals) <= 5

    producer_lookup = get_normalized_lookup("producer", DEFAULT_DATASET_PATH)
    assert isinstance(producer_lookup, dict)
    assert len(producer_lookup) > 0

    country_column = get_canonical_column("country", DEFAULT_DATASET_PATH)
    assert country_column == metadata.canonical_columns["country"]


def main() -> None:
    test_metadata_loads()
    test_core_text_fields_exist()
    test_text_field_values_are_non_empty()
    test_normalized_lookups_exist()
    test_top_values_exist()
    test_numeric_ranges_exist_when_columns_exist()
    test_public_helper_functions()

    print("All metadata smoke tests passed.")


if __name__ == "__main__":
    main()