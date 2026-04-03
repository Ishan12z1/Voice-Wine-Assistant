from __future__ import annotations

from backend.core.schemas import Occasion
from backend.core.schemas import QueryFilters
from backend.core.schemas import QueryIntent
from backend.core.schemas import SortBy
from backend.core.schemas import StructuredWineQuery
from backend.core.schemas import WineColor


# These are the filter fields Step 4 is allowed to populate.
SUPPORTED_FILTER_FIELDS = [
    "name",
    "producer",
    "country",
    "region",
    "appellation",
    "varietal",
    "color",
    "min_price",
    "max_price",
    "min_vintage",
    "max_vintage",
    "min_abv",
    "max_abv",
    "volume_ml",
    "min_best_score",
    "min_avg_score",
    "min_rating_count",
    "require_varietal",
    "require_vintage",
]


def make_query(
    question: str,
    *,
    intent: QueryIntent = QueryIntent.BROWSE_COLLECTION,
    filters: QueryFilters | None = None,
    sort_by: SortBy = SortBy.RELEVANCE,
    limit: int = 10,
    confidence: float = 1.0,
    occasion: Occasion | None = None,
) -> StructuredWineQuery:
    # Small helper so all returned queries have one consistent shape.
    return StructuredWineQuery(
        original_question=question,
        intent=intent,
        filters=filters or QueryFilters(),
        sort_by=sort_by,
        limit=limit,
        confidence=confidence,
        occasion=occasion,
    )


def make_ambiguous_query(
    question: str,
    *,
    missing_fields: list[str],
    clarification_message: str,
    confidence: float = 0.4,
) -> StructuredWineQuery:
    # Used when the question is too vague to parse confidently.
    return StructuredWineQuery(
        original_question=question,
        intent=QueryIntent.AMBIGUOUS_REQUEST,
        filters=QueryFilters(),
        sort_by=SortBy.RELEVANCE,
        limit=10,
        confidence=confidence,
        needs_clarification=True,
        clarification_message=clarification_message,
        missing_fields=missing_fields,
    )


def make_unsupported_query(
    question: str,
    *,
    reason: str,
    confidence: float = 1.0,
) -> StructuredWineQuery:
    # Used when the request asks for knowledge outside the dataset.
    return StructuredWineQuery(
        original_question=question,
        intent=QueryIntent.UNSUPPORTED_REQUEST,
        filters=QueryFilters(),
        sort_by=SortBy.RELEVANCE,
        limit=10,
        confidence=confidence,
        unsupported_reason=reason,
    )


def parse_query(text: str) -> StructuredWineQuery:
    """
    Step 3 placeholder.

    Step 4 will replace this body with real rule-based parsing using:
    - regex for budgets and numeric constraints
    - keyword detection for sort / recommendation intent
    - lookup and fuzzy matching for country, region, appellation, producer, varietal
    - color extraction
    - ambiguity / unsupported detection

    For now, we only guarantee one stable return contract.
    """
    cleaned = " ".join(text.strip().split())

    if not cleaned:
        return make_ambiguous_query(
            question=text or " ",
            missing_fields=["question"],
            clarification_message="Please ask about a wine, region, producer, budget, or another dataset field.",
        )

    # Step 3 does not try to interpret meaning yet.
    return make_query(
        question=cleaned,
        intent=QueryIntent.BROWSE_COLLECTION,
        filters=QueryFilters(),
        sort_by=SortBy.RELEVANCE,
        limit=10,
        confidence=0.5,
    )


if __name__ == "__main__":
    # Tiny smoke-test examples for local debugging.
    examples = [
        "Best-rated red wines under $50",
        "Show me Cabernet Sauvignon from California",
        "Find wines from Stag's Leap Wine Cellars",
        "Recommend a housewarming gift",
        "",
    ]

    for question in examples:
        result = parse_query(question)
        print(result.model_dump())