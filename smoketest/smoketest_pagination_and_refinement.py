from __future__ import annotations

import pandas as pd

from backend.core.data_loader import DEFAULT_DATASET_PATH, load_wine_dataset
from backend.services.pipeline import run_query_pipeline


def test_pagination_first_page(df: pd.DataFrame) -> None:
    """
    Page 1 should return a bounded slice and paging metadata.
    """
    response = run_query_pipeline(
        "best red wine from France",
        df,
        page_override=1,
        page_size_override=3,
    )

    assert response["response_type"] == "results"
    assert response["show_results"] is True
    assert response["page"] == 1
    assert response["page_size"] == 3
    assert response["returned_count"] <= 3
    assert response["total_matches"] > 0
    assert response["total_pages"] >= 1


def test_pagination_second_page(df: pd.DataFrame) -> None:
    """
    Page 2 should return the next slice when multiple pages exist.
    """
    response = run_query_pipeline(
        "best red wine from France",
        df,
        page_override=2,
        page_size_override=3,
    )

    assert response["page"] >= 1
    assert response["page_size"] == 3
    assert "has_prev_page" in response
    assert "has_next_page" in response


def test_soft_refinement_still_shows_results(df: pd.DataFrame) -> None:
    """
    Broad browse queries should now show results on page 1 while also
    marking the response as refinable.
    """
    response = run_query_pipeline(
        "show me wines",
        df,
        page_override=1,
        page_size_override=10,
    )

    assert response["response_type"] == "results"
    assert response["show_results"] is True
    assert response["returned_count"] > 0
    assert response["total_matches"] > 0
    assert response["needs_refinement"] is True


def test_soft_refinement_summary_mentions_page(df: pd.DataFrame) -> None:
    """
    The summary for broad queries should mention that a page is being shown
    and that the query can be narrowed further.
    """
    response = run_query_pipeline(
        "show me wines",
        df,
        page_override=1,
        page_size_override=10,
    )

    assert "page 1" in response["summary"].lower()
    assert "narrow" in response["summary"].lower()


def main() -> None:
    df = load_wine_dataset(DEFAULT_DATASET_PATH)

    test_pagination_first_page(df)
    test_pagination_second_page(df)
    test_soft_refinement_still_shows_results(df)
    test_soft_refinement_summary_mentions_page(df)

    print("All pagination and soft-refinement smoke tests passed.")


if __name__ == "__main__":
    main()