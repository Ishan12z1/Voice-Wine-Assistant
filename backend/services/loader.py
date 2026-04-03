from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


# Maps raw CSV column names to the normalized internal schema
RAW_TO_CANONICAL_COLUMNS = {
    "Id": "wine_id",
    "Name": "name",
    "Producer": "producer",
    "Country": "country",
    "Region": "region",
    "Appellation": "appellation",
    "Varietal": "varietal",
    "Retail": "price",
    "ABV": "abv",
    "Vintage": "vintage",
    "Upc": "upc",
    "color": "color",
    "image_url": "image_url",
    "professional_ratings": "professional_ratings_raw",
    "reference_url": "reference_url",
    "volume_ml": "volume_ml",
}

# Normalized color values
COLOR_MAP = {
    "red": "red",
    "white": "white",
    "sparkling": "sparkling",
    "rose": "rose",
    "rosé": "rose",
    "fortified": "fortified",
    "dessert": "dessert",
    "other": "other",
}


def normalize_whitespace(value: Any) -> Any:
    """Trim leading/trailing spaces and collapse repeated whitespace."""
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text if text else pd.NA


def smart_title(value: Any) -> Any:
    """
    Clean text and title-case only ALL-CAPS strings.
    Example: 'TOSCANA' -> 'Toscana', but 'Rioja Alta' stays unchanged.
    """
    value = normalize_whitespace(value)
    if pd.isna(value):
        return pd.NA

    text = str(value)

    # Only title-case all-caps values
    if text.isupper():
        text = text.title()

    return text


def clean_price(value: Any) -> float | None:
    """Extract a numeric price and round to 2 decimals."""
    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return round(float(value), 2)

    text = str(value).strip()
    text = text.replace("$", "").replace(",", "")
    match = re.search(r"-?\d+(\.\d+)?", text)
    if not match:
        return None

    return round(float(match.group()), 2)


def clean_integer(value: Any) -> Any:
    """Convert a value to integer where possible; otherwise return pd.NA."""
    if pd.isna(value):
        return pd.NA
    try:
        return int(float(value))
    except Exception:
        return pd.NA


def clean_float(value: Any) -> Any:
    """Convert a value to float where possible; otherwise return pd.NA."""
    if pd.isna(value):
        return pd.NA
    try:
        return round(float(value), 2)
    except Exception:
        return pd.NA


def normalize_color(value: Any) -> Any:
    """Normalize color labels to a controlled vocabulary."""
    value = normalize_whitespace(value)
    if pd.isna(value):
        return pd.NA

    key = str(value).lower()
    return COLOR_MAP.get(key, key)


def normalize_varietal(value: Any) -> Any:
    """Normalize varietal labels and preserve standard wine naming."""
    value = smart_title(value)
    if pd.isna(value):
        return pd.NA

    text = str(value)
    text = text.replace("Rose Blend", "Rosé Blend")
    return text


def parse_ratings_blob(blob: Any) -> list[dict]:
    """
    Parse the professional ratings field.
    Supports both JSON strings and Python literal-style strings.
    """
    if pd.isna(blob):
        return []

    text = str(blob).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        pass

    try:
        parsed = ast.literal_eval(text)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def extract_rating_stats(blob: Any) -> pd.Series:
    """
    Convert the ratings blob into summary statistics:
    - best_score
    - avg_score
    - rating_count
    - rating_sources
    """
    ratings = parse_ratings_blob(blob)

    normalized_scores = []
    sources = []

    for item in ratings:
        if not isinstance(item, dict):
            continue

        score = item.get("score")
        max_score = item.get("max_score", 100)
        source = item.get("source")

        try:
            score = float(score)
            max_score = float(max_score) if max_score else 100.0
            if max_score > 0:
                normalized_scores.append(round((score / max_score) * 100, 2))
        except Exception:
            pass

        if source:
            sources.append(str(source).strip())

    if not normalized_scores:
        return pd.Series(
            {
                "best_score": pd.NA,
                "avg_score": pd.NA,
                "rating_count": 0,
                "rating_sources": pd.NA,
            }
        )

    return pd.Series(
        {
            "best_score": round(max(normalized_scores), 2),
            "avg_score": round(sum(normalized_scores) / len(normalized_scores), 2),
            "rating_count": len(normalized_scores),
            "rating_sources": " | ".join(sorted(set(sources))) if sources else pd.NA,
        }
    )


def build_search_text(row: pd.Series) -> str:
    """Build a lowercase search field from important descriptive columns."""
    parts = [
        row.get("name"),
        row.get("producer"),
        row.get("country"),
        row.get("region"),
        row.get("appellation"),
        row.get("varietal"),
        row.get("color"),
        str(row.get("vintage")) if pd.notna(row.get("vintage")) else None,
    ]
    tokens = [str(x).strip().lower() for x in parts if pd.notna(x) and str(x).strip()]
    return " ".join(tokens)


def load_raw_wines(raw_csv_path: str | Path) -> pd.DataFrame:
    """Load the raw wine CSV and rename columns to the canonical schema."""
    df = pd.read_csv(raw_csv_path)
    df = df.rename(columns=RAW_TO_CANONICAL_COLUMNS)
    return df


def build_clean_wines(df: pd.DataFrame) -> pd.DataFrame:
    """Create the cleaned wine dataset with standardized fields."""
    clean = df.copy()

    clean["name"] = clean["name"].apply(normalize_whitespace)
    clean["producer"] = clean["producer"].apply(normalize_whitespace)

    clean["country"] = clean["country"].apply(smart_title)
    clean["region"] = clean["region"].apply(smart_title)
    clean["appellation"] = clean["appellation"].apply(smart_title)
    clean["varietal"] = clean["varietal"].apply(normalize_varietal)
    clean["color"] = clean["color"].apply(normalize_color)

    clean["price"] = clean["price"].apply(clean_price)
    clean["abv"] = clean["abv"].apply(clean_float)
    clean["vintage"] = clean["vintage"].apply(clean_integer)
    clean["upc"] = clean["upc"].apply(clean_integer)
    clean["volume_ml"] = clean["volume_ml"].apply(clean_integer)

    clean["image_url"] = clean["image_url"].apply(normalize_whitespace)
    clean["reference_url"] = clean["reference_url"].apply(normalize_whitespace)
    clean["professional_ratings_raw"] = clean["professional_ratings_raw"].apply(normalize_whitespace)

    ordered_cols = [
        "wine_id",
        "name",
        "producer",
        "country",
        "region",
        "appellation",
        "varietal",
        "color",
        "vintage",
        "price",
        "abv",
        "volume_ml",
        "upc",
        "image_url",
        "reference_url",
        "professional_ratings_raw",
    ]

    return clean[ordered_cols].copy()


def build_enriched_wines(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Add derived fields and rating statistics to the cleaned dataset."""
    enriched = clean_df.copy()

    rating_stats = enriched["professional_ratings_raw"].apply(extract_rating_stats)
    enriched = pd.concat([enriched, rating_stats], axis=1)

    enriched["has_varietal"] = enriched["varietal"].notna()
    enriched["has_vintage"] = enriched["vintage"].notna()
    enriched["search_text"] = enriched.apply(build_search_text, axis=1)

    return enriched


def inspect_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Return a column-level missing value and dtype summary."""
    summary = pd.DataFrame(
        {
            "missing_count": df.isna().sum(),
            "missing_pct": (df.isna().mean() * 100).round(1),
            "dtype": df.dtypes.astype(str),
        }
    ).sort_values(["missing_count", "missing_pct"], ascending=False)

    return summary


def save_step2_outputs(
    raw_csv_path: str | Path,
    clean_csv_path: str | Path,
    enriched_csv_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load the raw dataset, generate clean and enriched outputs,
    and save both CSV files.
    """
    raw_df = load_raw_wines(raw_csv_path)
    clean_df = build_clean_wines(raw_df)
    enriched_df = build_enriched_wines(clean_df)

    Path(clean_csv_path).parent.mkdir(parents=True, exist_ok=True)
    Path(enriched_csv_path).parent.mkdir(parents=True, exist_ok=True)

    clean_df.to_csv(clean_csv_path, index=False)
    enriched_df.to_csv(enriched_csv_path, index=False)

    return clean_df, enriched_df


def parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments.

    Defaults are the same as the current hardcoded paths.
    """
    root = Path(__file__).resolve().parents[2]

    default_raw_path = root / "data" / "raw" / "Assignment wine dataset - Sheet1.csv"
    default_clean_path = root / "data" / "processed" / "wines_clean.csv"
    default_enriched_path = root / "data" / "processed" / "wines_enriched.csv"

    parser = argparse.ArgumentParser(
        description="Clean and enrich the wine dataset, then save processed CSV files."
    )

    parser.add_argument(
        "--raw-path",
        type=Path,
        default=default_raw_path,
        help=f"Path to the raw input CSV file. Default: {default_raw_path}",
    )
    parser.add_argument(
        "--clean-path",
        type=Path,
        default=default_clean_path,
        help=f"Path to save the cleaned CSV file. Default: {default_clean_path}",
    )
    parser.add_argument(
        "--enriched-path",
        type=Path,
        default=default_enriched_path,
        help=f"Path to save the enriched CSV file. Default: {default_enriched_path}",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    raw_df = load_raw_wines(args.raw_path)
    clean_df, enriched_df = save_step2_outputs(
        raw_csv_path=args.raw_path,
        clean_csv_path=args.clean_path,
        enriched_csv_path=args.enriched_path,
    )

    print("\nRAW SHAPE:", raw_df.shape)
    print("CLEAN SHAPE:", clean_df.shape)
    print("ENRICHED SHAPE:", enriched_df.shape)

    print("\nMISSING VALUE SUMMARY:")
    print(inspect_dataset(raw_df).to_string())

    print("\nCOLOR COUNTS:")
    print(clean_df["color"].value_counts(dropna=False).to_string())

    print("\nTOP ENRICHED COLUMNS:")
    print(
        enriched_df[
            ["name", "price", "color", "varietal", "best_score", "avg_score", "rating_count"]
        ]
        .head(10)
        .to_string(index=False)
    )