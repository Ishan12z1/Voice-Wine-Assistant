from __future__ import annotations

from backend.core.schemas import (
    Occasion,
    QueryFilters,
    QueryIntent,
    SortBy,
    StructuredWineQuery,
)


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
    """
    Build a normal structured query object.

    This is used when the parser has enough information to run retrieval.
    """
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
    filters: QueryFilters | None = None,
    sort_by: SortBy = SortBy.RELEVANCE,
    occasion: Occasion | None = None,
) -> StructuredWineQuery:
    """
    Build a structured query that explicitly asks the user for clarification.

    Important:
    - preserve partial filters already extracted
    - preserve sort and occasion when available
    """
    return StructuredWineQuery(
        original_question=question,
        intent=QueryIntent.AMBIGUOUS_REQUEST,
        filters=filters or QueryFilters(),
        sort_by=sort_by,
        limit=10,
        confidence=confidence,
        needs_clarification=True,
        clarification_message=clarification_message,
        missing_fields=missing_fields,
        occasion=occasion,
    )


def make_unsupported_query(
    question: str,
    *,
    reason: str,
    confidence: float = 1.0,
) -> StructuredWineQuery:
    """
    Build a structured query for requests that are outside the app scope.
    """
    return StructuredWineQuery(
        original_question=question,
        intent=QueryIntent.UNSUPPORTED_REQUEST,
        filters=QueryFilters(),
        sort_by=SortBy.RELEVANCE,
        limit=10,
        confidence=confidence,
        unsupported_reason=reason,
    )