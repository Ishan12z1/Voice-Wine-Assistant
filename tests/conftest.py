from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.main import app
from backend.core.data_loader import load_wine_dataset
from backend.core.settings import get_configured_dataset_path
from backend.services.loader import build_clean_wines, build_enriched_wines, load_raw_wines


RAW_DATASET_PATH = PROJECT_ROOT / "data" / "raw" / "Assignment wine dataset - Sheet1.csv"


@pytest.fixture(scope="session")
def raw_dataset_path() -> Path:
    return RAW_DATASET_PATH


@pytest.fixture(scope="session")
def processed_dataset_path() -> str:
    return get_configured_dataset_path()


@pytest.fixture(scope="session")
def raw_df(raw_dataset_path):
    return load_raw_wines(raw_dataset_path)


@pytest.fixture(scope="session")
def clean_df(raw_df):
    return build_clean_wines(raw_df)


@pytest.fixture(scope="session")
def enriched_df(clean_df):
    return build_enriched_wines(clean_df)


@pytest.fixture(scope="session")
def production_df():
    return load_wine_dataset(get_configured_dataset_path())


@pytest.fixture()
def api_client():
    with TestClient(app) as client:
        yield client
