from __future__ import annotations

from backend.core.schemas import QueryFilters, QueryIntent, SortBy, StructuredWineQuery
from backend.services.parser.builders import (
    make_ambiguous_query,
    make_query,
    make_unsupported_query,
)
from backend.services.parser.extractors import (
    detect_color,
    detect_occasion,
    detect_sort_preference,
    detect_unsupported_reason,
    extract_abv_filters,
    extract_limit,
    extract_price_filters,
    extract_score_filters,
    extract_vintage_filters,
    extract_volume_ml,
    mentions_varietal_focus,
    should_ask_for_clarification,
)
from backend.services.parser.matching import apply_dataset_matches


def infer_intent(
    question: str,
    filters: QueryFilters,
    occasion,
    detected_sort: SortBy,
) -> QueryIntent:
    """
    Infer the main query intent after extraction/matching is complete.
    """
    if occasion is not None:
        return QueryIntent.GIFT_RECOMMENDATION

    if detected_sort == SortBy.PRICE_ASC:
        return QueryIntent.CHEAPEST

    if detected_sort == SortBy.PRICE_DESC:
        return QueryIntent.MOST_EXPENSIVE

    if detected_sort == SortBy.BEST_SCORE_DESC and filters.max_price is not None:
        return QueryIntent.BEST_RATED_UNDER_BUDGET

    return QueryIntent.BROWSE_COLLECTION


def parse_query(text: str) -> StructuredWineQuery:
    """
    Main parser entrypoint.

    This coordinates:
    - unsupported detection
    - numeric extraction
    - color/occasion extraction
    - dataset-backed matching
    - clarification checks
    - final intent inference
    """
    cleaned = " ".join(text.strip().split())

    if not cleaned:
        return make_ambiguous_query(
            question="[empty question]",
            missing_fields=["question"],
            clarification_message=(
                "Please ask about a wine, producer, region, appellation, "
                "budget, rating, or another dataset field."
            ),
            filters=QueryFilters(),
            sort_by=SortBy.RELEVANCE,
            occasion=None,
            unresolved_entities=[],
        )

    unsupported_reason = detect_unsupported_reason(cleaned)
    if unsupported_reason:
        return make_unsupported_query(
            question=cleaned,
            reason=unsupported_reason,
            confidence=0.99,
            unresolved_entities=[],
        )

    filters = QueryFilters()
    confidence_parts: list[float] = []

    # Numeric filters first
    min_best_score, score_conf = extract_score_filters(cleaned)
    filters.min_best_score = min_best_score
    if score_conf is not None:
        confidence_parts.append(score_conf)

    min_vintage, max_vintage, vintage_conf = extract_vintage_filters(cleaned)
    filters.min_vintage = min_vintage
    filters.max_vintage = max_vintage
    if vintage_conf is not None:
        confidence_parts.append(vintage_conf)

    min_abv, max_abv, abv_conf = extract_abv_filters(cleaned)
    filters.min_abv = min_abv
    filters.max_abv = max_abv
    if abv_conf is not None:
        confidence_parts.append(abv_conf)

    volume_ml, volume_conf = extract_volume_ml(cleaned)
    filters.volume_ml = volume_ml
    if volume_conf is not None:
        confidence_parts.append(volume_conf)

    # Color and occasion
    color, color_conf = detect_color(cleaned)
    filters.color = color
    if color_conf is not None:
        confidence_parts.append(color_conf)

    occasion, occasion_conf = detect_occasion(cleaned)
    if occasion_conf is not None:
        confidence_parts.append(occasion_conf)

    # Dataset-backed entity matching + unresolved entity detection
    filters, match_scores, unresolved_entities = apply_dataset_matches(cleaned, filters)
    confidence_parts.extend(match_scores)

    # Require varietal data when the prompt explicitly depends on grape/varietal.
    if mentions_varietal_focus(cleaned):
        filters.require_varietal = True

    if filters.varietal:
        filters.require_varietal = True

    # Price parsing comes after other numeric fields to avoid conflicts.
    has_non_price_numeric = any([
        filters.min_best_score is not None,
        filters.min_vintage is not None,
        filters.max_vintage is not None,
        filters.min_abv is not None,
        filters.max_abv is not None,
        filters.volume_ml is not None,
    ])

    min_price, max_price, price_conf = extract_price_filters(
        cleaned,
        allow_lenient_price=not has_non_price_numeric,
    )
    filters.min_price = min_price
    filters.max_price = max_price
    if price_conf is not None:
        confidence_parts.append(price_conf)

    limit = extract_limit(cleaned) or 10

    detected_sort, sort_conf = detect_sort_preference(cleaned)
    if sort_conf is not None:
        confidence_parts.append(sort_conf)

    # Clarification flow
    should_clarify, missing_fields, clarification_message = should_ask_for_clarification(
        cleaned, filters, occasion, detected_sort
    )
    if should_clarify:
        return make_ambiguous_query(
            question=cleaned,
            missing_fields=missing_fields,
            clarification_message=clarification_message or (
                "Please add one detail like budget, color, region, producer, "
                "appellation, or varietal."
            ),
            confidence=0.45,
            filters=filters,
            sort_by=detected_sort,
            occasion=occasion,
            unresolved_entities=unresolved_entities,
        )

    # Intent inference
    intent = infer_intent(cleaned, filters, occasion, detected_sort)

    # Confidence score from detected signals
    confidence = round(sum(confidence_parts) / len(confidence_parts), 2) if confidence_parts else 0.55

    # Preserve score-based sorting for broad "best wine" style prompts.
    if detected_sort == SortBy.BEST_SCORE_DESC and intent == QueryIntent.BROWSE_COLLECTION:
        sort_by = SortBy.BEST_SCORE_DESC
    else:
        sort_by = detected_sort

    return make_query(
        question=cleaned,
        intent=intent,
        filters=filters,
        sort_by=sort_by,
        limit=limit,
        confidence=confidence,
        occasion=occasion,
        unresolved_entities=unresolved_entities,
    )