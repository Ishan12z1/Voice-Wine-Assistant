"""
smoketest_api.py

This file runs a simple end-to-end smoke test against the FastAPI app.
It verifies that:
- the API starts
- /health returns dataset info
- /query returns results for a known-positive query
- /query returns no_results for a known-impossible query
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

# Point the API to the Step 2 enriched dataset.
# Change this if your processed file lives somewhere else.
DATASET_PATH = "data/processed/wines_enriched.csv"

# Set the environment variable before making requests.
os.environ["WINE_DATASET_PATH"] = DATASET_PATH

from backend.api.main import app
from backend.core.data_loader import load_wine_dataset


def print_response_preview(label: str, response_json: dict) -> None:
    """
    Print a compact preview of an API response.
    """
    print(f"\n=== {label} ===")
    print(f"response_type: {response_json.get('response_type')}")
    print(f"summary: {response_json.get('summary')}")
    print(f"total_matches: {response_json.get('total_matches')}")
    print(f"returned_count: {response_json.get('returned_count')}")
    print(f"show_results: {response_json.get('show_results')}")

    wines = response_json.get("wines", [])[:3]
    for i, wine in enumerate(wines, start=1):
        print(
            f"{i}. "
            f"name={wine.get('name')} | "
            f"price={wine.get('price')} | "
            f"color={wine.get('color')} | "
            f"best_score={wine.get('best_score')} | "
            f"avg_score={wine.get('avg_score')}"
        )


def test_health(client: TestClient) -> None:
    """
    Smoke test:
    - /health should return 200
    - dataset should be loaded
    """
    response = client.get("/health")
    assert response.status_code == 200, f"/health failed: {response.text}"

    data = response.json()
    assert data["status"] == "ok"
    assert data["rows_loaded"] > 0
    assert data["columns_loaded"] > 0

    print("\n=== health ===")
    print(data)


def test_query_positive(client: TestClient) -> None:
    """
    Smoke test:
    - known-positive query should return results
    - returned wines should satisfy the obvious filters
    """
    payload = {
        "question": "Best-rated red wines under $50",
        "limit": 5,
    }

    response = client.post("/query", json=payload)
    assert response.status_code == 200, f"/query positive failed: {response.text}"

    data = response.json()

    assert data["response_type"] == "results"
    assert data["show_results"] is True
    assert data["total_matches"] > 0
    assert data["returned_count"] > 0
    assert len(data["wines"]) > 0

    for wine in data["wines"]:
        assert wine.get("color") == "red", f"Expected red wine, got: {wine.get('color')}"
        assert wine.get("price") is not None and wine["price"] <= 50, f"Expected price <= 50, got: {wine.get('price')}"
        assert wine.get("best_score") is not None, f"Expected best_score to be populated, got: {wine.get('best_score')}"

    print_response_preview("positive query", data)


def test_query_no_results(client: TestClient) -> None:
    """
    Smoke test:
    - known-impossible query should return no_results
    """
    payload = {
        "question": "Show me red wines from Mars under $2",
        "limit": 5,
    }

    response = client.post("/query", json=payload)
    assert response.status_code == 200, f"/query no-results failed: {response.text}"

    data = response.json()

    assert data["response_type"] == "no_results"
    assert data["show_results"] is False
    assert data["total_matches"] == 0
    assert data["returned_count"] == 0
    assert data["wines"] == []

    print_response_preview("no-results query", data)


def main() -> None:
    """
    Run all Step 7 API smoke tests.
    """
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(
            f"Processed dataset not found at '{DATASET_PATH}'. "
            "Run your Step 2 script first or fix DATASET_PATH in this file."
        )

    # Clear any cached dataset so the test uses the env path above.
    load_wine_dataset.cache_clear()

    client = TestClient(app)

    test_health(client)
    test_query_positive(client)
    test_query_no_results(client)

    print("\nAll Step 7 API smoke tests passed.")


if __name__ == "__main__":
    main()