from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd
from rapidfuzz import fuzz, process

from backend.core.data_loader import DEFAULT_DATASET_PATH, load_wine_dataset
from backend.core.schemas import (
    DatasetFieldMetadata,
    DatasetMetadata,
    DatasetNumericRangeMetadata,
)
from backend.utils.helpers import best_value_match, normalize_text


# App-level canonical field names mapped to possible dataframe column names.
CANONICAL_FIELD_CANDIDATES: dict[str, list[str]] = {
    "name": ["name", "Name"],
    "producer": ["producer", "Producer"],
    "country": ["country", "Country"],
    "region": ["region", "Region"],
    "appellation": ["appellation", "Appellation"],
    "varietal": ["varietal", "Varietal"],
    "color": ["color", "Color"],
    "price": ["price", "Retail"],
    "vintage": ["vintage", "Vintage"],
    "abv": ["abv", "ABV"],
    "volume_ml": ["volume_ml"],
    "best_score": ["best_score"],
    "avg_score": ["avg_score"],
    "rating_count": ["rating_count"],
    "image_url": ["image_url"],
    "reference_url": ["reference_url"],
}

TEXT_FIELDS = [
    "name",
    "producer",
    "country",
    "region",
    "appellation",
    "varietal",
    "color",
]

NUMERIC_FIELDS = [
    "price",
    "vintage",
    "abv",
    "volume_ml",
    "best_score",
    "avg_score",
    "rating_count",
]

FIELD_MATCH_CONFIG: dict[str, dict[str, float | bool]] = {
    "country": {"score_cutoff": 96, "allow_fuzzy": True},
    "region": {"score_cutoff": 94, "allow_fuzzy": True},
    "appellation": {"score_cutoff": 94, "allow_fuzzy": True},
    "producer": {"score_cutoff": 93, "allow_fuzzy": True},
    "varietal": {"score_cutoff": 92, "allow_fuzzy": True},
    "name": {"score_cutoff": 97, "allow_fuzzy": False},
    "color": {"score_cutoff": 100, "allow_fuzzy": False},
}


def _resolve_dataset_path(dataset_path: str | None = None) -> str:
    """
    Resolve the active dataset path using the same fallback behavior as the loader.
    """
    return dataset_path or os.getenv("WINE_DATASET_PATH", DEFAULT_DATASET_PATH)


def _resolve_canonical_column(df: pd.DataFrame, field_name: str) -> str | None:
    """
    Find the first dataframe column that matches the canonical app field.
    """
    candidates = CANONICAL_FIELD_CANDIDATES.get(field_name, [])
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _extract_text_field_metadata(
    df: pd.DataFrame,
    field_name: str,
    column_name: str | None,
) -> DatasetFieldMetadata:
    """
    Build metadata for one text/categorical field.
    """
    if column_name is None:
        return DatasetFieldMetadata(
            field_name=field_name,
            canonical_column=None,
        )

    values_series = (
        df[column_name]
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = [value for value in values_series.tolist() if value]
    if not values:
        return DatasetFieldMetadata(
            field_name=field_name,
            canonical_column=column_name,
        )

    counts: dict[str, int] = {}
    normalized_to_canonical: dict[str, str] = {}

    for value in values:
        counts[value] = counts.get(value, 0) + 1

        normalized_value = normalize_text(value)
        if normalized_value and normalized_value not in normalized_to_canonical:
            normalized_to_canonical[normalized_value] = value

    unique_values = sorted(
        set(values),
        key=lambda value: (-len(value), value.lower()),
    )

    top_values = sorted(
        counts.keys(),
        key=lambda value: (-counts[value], value.lower()),
    )[:10]

    return DatasetFieldMetadata(
        field_name=field_name,
        canonical_column=column_name,
        values=unique_values,
        normalized_to_canonical=normalized_to_canonical,
        counts=counts,
        top_values=top_values,
    )


def _extract_numeric_range_metadata(
    df: pd.DataFrame,
    field_name: str,
    column_name: str | None,
) -> DatasetNumericRangeMetadata:
    """
    Build numeric min/max metadata for one field.
    """
    if column_name is None:
        return DatasetNumericRangeMetadata(
            field_name=field_name,
            canonical_column=None,
        )

    numeric_series = pd.to_numeric(df[column_name], errors="coerce").dropna()

    if numeric_series.empty:
        return DatasetNumericRangeMetadata(
            field_name=field_name,
            canonical_column=column_name,
            min_value=None,
            max_value=None,
        )

    min_value = numeric_series.min()
    max_value = numeric_series.max()

    # Keep ints as ints where possible, otherwise floats.
    def _clean_number(value: float | int) -> float | int:
        float_value = float(value)
        return int(float_value) if float_value.is_integer() else float_value

    return DatasetNumericRangeMetadata(
        field_name=field_name,
        canonical_column=column_name,
        min_value=_clean_number(min_value),
        max_value=_clean_number(max_value),
    )


@lru_cache(maxsize=4)
def _build_dataset_metadata(resolved_path: str, dataset_mtime: float) -> DatasetMetadata:
    """
    Internal cached builder keyed by dataset path + modification time.

    If the dataset file changes, the mtime changes, and the cache refreshes.
    """
    df = load_wine_dataset(resolved_path)

    canonical_columns = {
        field_name: _resolve_canonical_column(df, field_name)
        for field_name in CANONICAL_FIELD_CANDIDATES
    }

    field_indexes = {
        field_name: _extract_text_field_metadata(
            df=df,
            field_name=field_name,
            column_name=canonical_columns[field_name],
        )
        for field_name in TEXT_FIELDS
    }

    numeric_ranges = {
        field_name: _extract_numeric_range_metadata(
            df=df,
            field_name=field_name,
            column_name=canonical_columns[field_name],
        )
        for field_name in NUMERIC_FIELDS
    }

    return DatasetMetadata(
        dataset_path=resolved_path,
        dataset_mtime=dataset_mtime,
        available_columns=list(df.columns),
        canonical_columns=canonical_columns,
        field_indexes=field_indexes,
        numeric_ranges=numeric_ranges,
    )


def get_dataset_metadata(dataset_path: str | None = None) -> DatasetMetadata:
    """
    Public entry point for metadata access.
    """
    resolved_path = _resolve_dataset_path(dataset_path)

    if not os.path.exists(resolved_path):
        raise FileNotFoundError(
            f"Wine dataset not found at: {resolved_path}. "
            "Set WINE_DATASET_PATH or generate the processed dataset first."
        )

    dataset_mtime = os.path.getmtime(resolved_path)
    return _build_dataset_metadata(resolved_path, dataset_mtime)


def get_field_values(field_name: str, dataset_path: str | None = None) -> list[str]:
    """
    Return all canonical values for one text field.
    """
    metadata = get_dataset_metadata(dataset_path)
    field_meta = metadata.field_indexes.get(field_name)

    if field_meta is None:
        return []

    return field_meta.values


def field_exists(field_name: str, dataset_path: str | None = None) -> bool:
    """
    Return True when the current dataset includes this canonical field.
    """
    metadata = get_dataset_metadata(dataset_path)
    return metadata.canonical_columns.get(field_name) is not None


def get_top_field_values(
    field_name: str,
    limit: int = 5,
    dataset_path: str | None = None,
) -> list[str]:
    """
    Return the most frequent values for one field, useful for UI suggestions.
    """
    metadata = get_dataset_metadata(dataset_path)
    field_meta = metadata.field_indexes.get(field_name)

    if field_meta is None:
        return []

    return field_meta.top_values[: max(limit, 0)]


def get_numeric_range(
    field_name: str,
    dataset_path: str | None = None,
) -> DatasetNumericRangeMetadata | None:
    """
    Return numeric range metadata for one field.
    """
    metadata = get_dataset_metadata(dataset_path)
    return metadata.numeric_ranges.get(field_name)


def get_normalized_lookup(
    field_name: str,
    dataset_path: str | None = None,
) -> dict[str, str]:
    """
    Return normalized_value -> canonical_value for one text field.
    """
    metadata = get_dataset_metadata(dataset_path)
    field_meta = metadata.field_indexes.get(field_name)

    if field_meta is None:
        return {}

    return field_meta.normalized_to_canonical


def get_canonical_column(
    field_name: str,
    dataset_path: str | None = None,
) -> str | None:
    """
    Return the actual dataframe column name for one canonical app field.
    """
    metadata = get_dataset_metadata(dataset_path)
    return metadata.canonical_columns.get(field_name)


def get_field_metadata(field_name: str, dataset_path: str | None = None) -> DatasetFieldMetadata | None:
    """
    Return the full metadata object for one field.
    """
    metadata = get_dataset_metadata(dataset_path)
    return metadata.field_indexes.get(field_name)


def get_field_match_config(field_name: str) -> dict[str, float | bool]:
    """
    Return the match behavior config for one field.
    """
    return FIELD_MATCH_CONFIG.get(field_name, {"score_cutoff": 92, "allow_fuzzy": True})


def get_closest_field_values(
    field_name: str,
    user_text: str,
    limit: int = 3,
    dataset_path: str | None = None,
) -> list[str]:
    """
    Return the closest grounded values for a field using normalized metadata.
    """
    field_meta = get_field_metadata(field_name, dataset_path)
    if field_meta is None or not field_meta.values or limit <= 0:
        return []

    normalized_input = normalize_text(user_text)
    if not normalized_input:
        return field_meta.top_values[:limit]

    normalized_keys = list(field_meta.normalized_to_canonical.keys())
    if not normalized_keys:
        return field_meta.top_values[:limit]

    matches = process.extract(
        normalized_input,
        normalized_keys,
        scorer=fuzz.WRatio,
        limit=max(limit * 2, limit),
    )

    suggestions: list[str] = []
    for normalized_value, score, _ in matches:
        if score < 55:
            continue

        canonical_value = field_meta.normalized_to_canonical.get(normalized_value)
        if canonical_value and canonical_value not in suggestions:
            suggestions.append(canonical_value)

        if len(suggestions) >= limit:
            break

    if suggestions:
        return suggestions

    return field_meta.top_values[:limit]


def resolve_field_value(
    field_name: str,
    user_text: str,
    dataset_path: str | None = None,
) -> tuple[str | None, float | None, list[str]]:
    """
    Resolve a user-provided text against one metadata-backed field.

    Returns:
    - canonical matched value, if any
    - match score, if any
    - fallback suggestions when no match is found
    """
    field_meta = get_field_metadata(field_name, dataset_path)
    if field_meta is None or field_meta.canonical_column is None:
        return None, None, []

    config = get_field_match_config(field_name)
    match = best_value_match(
        user_text,
        field_meta.values,
        score_cutoff=float(config["score_cutoff"]),
        allow_fuzzy=bool(config["allow_fuzzy"]),
    )
    if match is not None:
        return match[0], match[1], []

    return None, None, get_closest_field_values(field_name, user_text, limit=3, dataset_path=dataset_path)
