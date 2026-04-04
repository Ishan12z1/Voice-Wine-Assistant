"""
data_loader.py

This file loads the processed enriched wine dataset for the API.

"""

from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

DEFAULT_DATASET_PATH = "data/processed/wines_enriched.csv"

NUMERIC_COLUMNS = [
    "price",
    "vintage",
    "abv",
    "volume_ml",
    "best_score",
    "avg_score",
    "rating_count",
]


@lru_cache(maxsize=1)
def load_wine_dataset(dataset_path: str | None = None) -> pd.DataFrame:
    """
    Load the enriched dataset once and coerce numeric columns.
    """
    resolved_path = dataset_path or os.getenv("WINE_DATASET_PATH", DEFAULT_DATASET_PATH)

    if not os.path.exists(resolved_path):
        raise FileNotFoundError(
            f"Wine dataset not found at: {resolved_path}. "
            "Set WINE_DATASET_PATH or generate Step 2 outputs first."
        )

    df = pd.read_csv(resolved_path)

    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df