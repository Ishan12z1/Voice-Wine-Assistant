from __future__ import annotations


def test_health_endpoint_reports_loaded_dataset(api_client) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["rows_loaded"] > 0
    assert payload["columns_loaded"] > 0


def test_query_endpoint_returns_results_payload(api_client) -> None:
    response = api_client.post(
        "/query",
        json={
            "question": "Best-rated red wines under $50",
            "page": 1,
            "page_size": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response_type"] == "results"
    assert payload["show_results"] is True
    assert payload["returned_count"] == 5
    assert isinstance(payload["wines"], list)


def test_query_endpoint_returns_grounded_no_results(api_client) -> None:
    response = api_client.post(
        "/query",
        json={
            "question": "best red wine in India",
            "page": 1,
            "page_size": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response_type"] == "no_results"
    assert payload["show_results"] is False
    assert payload["query"]["unresolved_entities"][0]["field"] == "country_or_region"


def test_query_endpoint_validates_request_shape(api_client) -> None:
    response = api_client.post(
        "/query",
        json={
            "question": "best red wine",
            "page": 0,
            "page_size": 100,
        },
    )

    assert response.status_code == 422


def test_query_endpoint_rejects_unknown_fields(api_client) -> None:
    response = api_client.post(
        "/query",
        json={
            "question": "best red wine",
            "unknown_field": "oops",
        },
    )

    assert response.status_code == 422
