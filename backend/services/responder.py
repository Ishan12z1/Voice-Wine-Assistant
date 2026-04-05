"""
responder.py

This file builds short, grounded natural-language responses from the retrieval
output. It does not search the dataset and it does not rank wines.
"""

from __future__ import annotations

from typing import Any

from backend.core.dataset_metadata import get_top_field_values
from backend.core.schemas import QueryIntent, SortBy, StructuredWineQuery, UnresolvedReason


def _pluralize(word: str, count: int) -> str:
    """
    Return a simple pluralized word for counts.
    """
    return word if count == 1 else f"{word}s"


def _format_price(value: float | int | None) -> str:
    """
    Format a price consistently for user-facing text.
    """
    if value is None:
        return ""
    return f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"


def _make_suggestion(label: str, value: str, mode: str = "append") -> dict[str, str]:
    return {
        "label": label,
        "value": value,
        "mode": mode,
    }


def _dedupe_suggestions(suggestions: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for suggestion in suggestions:
        key = (
            suggestion.get("label", ""),
            suggestion.get("value", ""),
            suggestion.get("mode", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)

    return deduped


def _normalize_suggestion_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _filter_suggestions_for_query(
    query: StructuredWineQuery,
    suggestions: list[dict[str, str]],
) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []

    active_color = _normalize_suggestion_text(query.filters.color.value if query.filters.color else None)
    active_country = _normalize_suggestion_text(query.filters.country)
    active_region = _normalize_suggestion_text(query.filters.region)
    active_appellation = _normalize_suggestion_text(query.filters.appellation)
    active_producer = _normalize_suggestion_text(query.filters.producer)
    active_varietal = _normalize_suggestion_text(query.filters.varietal)
    active_name = _normalize_suggestion_text(query.filters.name)

    for suggestion in suggestions:
        mode = suggestion.get("mode", "")
        value = _normalize_suggestion_text(suggestion.get("value"))

        if mode == "color" and value == active_color:
            continue

        if mode == "varietal" and value == active_varietal:
            continue

        if mode == "append":
            if active_country and value == f"from {active_country}":
                continue
            if active_region and value == f"from {active_region}":
                continue
            if active_appellation and value == f"from {active_appellation}":
                continue
            if active_producer and value == f"from {active_producer}":
                continue
            if active_name and value == f"called {active_name}":
                continue

        filtered.append(suggestion)

    return filtered


def _build_field_value_suggestions(field_name: str, values: list[str]) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []

    for value in values:
        if field_name in {"country", "region", "appellation", "country_or_region"}:
            suggestions.append(_make_suggestion(value, f"from {value}", "append"))
        elif field_name == "producer":
            suggestions.append(_make_suggestion(value, f"from {value}", "append"))
        elif field_name == "varietal":
            suggestions.append(_make_suggestion(value, value, "varietal"))
        elif field_name == "color":
            suggestions.append(_make_suggestion(value.title(), value, "color"))
        elif field_name == "name":
            suggestions.append(_make_suggestion(value, f"called {value}", "append"))
        else:
            suggestions.append(_make_suggestion(value, value, "append"))

    return suggestions


def _build_clarification_suggestions(query: StructuredWineQuery) -> list[dict[str, str]]:
    missing_fields = query.missing_fields

    if "budget" in missing_fields:
        return [
            _make_suggestion("Under $25", "under $25", "budget"),
            _make_suggestion("Under $50", "under $50", "budget"),
            _make_suggestion("Between $30 and $60", "between $30 and $60", "budget"),
        ]

    if "color" in missing_fields:
        colors = get_top_field_values("color", limit=4)
        return _build_field_value_suggestions("color", colors or ["red", "white", "sparkling", "rose"])

    if "varietal" in missing_fields:
        return _build_field_value_suggestions("varietal", get_top_field_values("varietal", limit=4))

    if "budget_or_style" in missing_fields:
        return _dedupe_suggestions(
            [
                _make_suggestion("Under $30", "under $30", "budget"),
                *_build_field_value_suggestions("color", get_top_field_values("color", limit=2)),
                *_build_field_value_suggestions("country", get_top_field_values("country", limit=2)),
            ]
        )[:4]

    return []


def _build_refinement_suggestions() -> list[dict[str, str]]:
    suggestions = [
        _make_suggestion("Under $30", "under $30", "budget"),
        *_build_field_value_suggestions("color", get_top_field_values("color", limit=2)),
        *_build_field_value_suggestions("country", get_top_field_values("country", limit=2)),
        *_build_field_value_suggestions("varietal", get_top_field_values("varietal", limit=2)),
    ]
    return _dedupe_suggestions(suggestions)[:6]


def _build_unresolved_suggestions(query: StructuredWineQuery) -> list[dict[str, str]]:
    if not query.unresolved_entities:
        return []

    first_entity = query.unresolved_entities[0]

    if first_entity.closest_matches:
        return _build_field_value_suggestions(first_entity.field, first_entity.closest_matches)

    if first_entity.reason == UnresolvedReason.FIELD_MISSING_FROM_DATASET:
        return _dedupe_suggestions(
            [
                *_build_field_value_suggestions("country", get_top_field_values("country", limit=2)),
                *_build_field_value_suggestions("color", get_top_field_values("color", limit=2)),
                *_build_field_value_suggestions("varietal", get_top_field_values("varietal", limit=2)),
            ]
        )[:6]

    fallback_field = "country" if first_entity.field == "country_or_region" else first_entity.field
    return _build_field_value_suggestions(fallback_field, get_top_field_values(fallback_field, limit=3))


def _build_no_results_suggestions() -> list[dict[str, str]]:
    return _dedupe_suggestions(
        [
            _make_suggestion("Under $50", "under $50", "budget"),
            *_build_field_value_suggestions("color", get_top_field_values("color", limit=2)),
            *_build_field_value_suggestions("country", get_top_field_values("country", limit=2)),
        ]
    )[:5]


def _describe_filters(query: StructuredWineQuery) -> str:
    """
    Convert active filters into a short human-readable description that fits
    naturally after the phrase 'matching wines'.
    """
    f = query.filters
    parts: list[str] = []

    if f.color is not None:
        parts.append(f"that are {f.color.value}")

    if f.varietal:
        parts.append(f"with varietal '{f.varietal}'")

    if f.producer:
        parts.append(f"from producer '{f.producer}'")

    if f.country:
        parts.append(f"from {f.country}")

    if f.region:
        parts.append(f"from {f.region}")

    if f.appellation:
        parts.append(f"from appellation '{f.appellation}'")

    if f.name:
        parts.append(f"matching '{f.name}'")

    if f.min_price is not None and f.max_price is not None:
        parts.append(f"priced between {_format_price(f.min_price)} and {_format_price(f.max_price)}")
    elif f.max_price is not None:
        parts.append(f"priced under {_format_price(f.max_price)}")
    elif f.min_price is not None:
        parts.append(f"priced at least {_format_price(f.min_price)}")

    if f.min_vintage is not None and f.max_vintage is not None:
        parts.append(f"from vintages {f.min_vintage} to {f.max_vintage}")
    elif f.min_vintage is not None:
        parts.append(f"from vintage {f.min_vintage} or newer")
    elif f.max_vintage is not None:
        parts.append(f"from vintage {f.max_vintage} or older")

    if f.min_abv is not None and f.max_abv is not None:
        parts.append(f"with ABV between {f.min_abv}% and {f.max_abv}%")
    elif f.min_abv is not None:
        parts.append(f"with ABV at least {f.min_abv}%")
    elif f.max_abv is not None:
        parts.append(f"with ABV up to {f.max_abv}%")

    if f.volume_ml is not None:
        parts.append(f"in {f.volume_ml}ml bottles")

    if f.min_best_score is not None:
        parts.append(f"with best score at least {f.min_best_score}")

    if f.min_avg_score is not None:
        parts.append(f"with average score at least {f.min_avg_score}")

    if f.min_rating_count is not None:
        parts.append(f"with at least {f.min_rating_count} ratings")

    if f.require_varietal:
        parts.append("with known varietal data")

    if f.require_vintage:
        parts.append("with known vintage data")

    if not parts:
        return "from the collection"

    return " ".join(parts)


def _describe_ranking(query: StructuredWineQuery) -> str:
    """
    Explain the ranking basis in plain English.
    """
    if query.sort_by == SortBy.BEST_SCORE_DESC:
        return "best score, with lower price breaking ties"

    if query.sort_by == SortBy.AVG_SCORE_DESC:
        return "average score, with lower price breaking ties"

    if query.sort_by == SortBy.PRICE_ASC:
        return "lowest price first"

    if query.sort_by == SortBy.PRICE_DESC:
        return "highest price first"

    if query.sort_by == SortBy.VALUE_DESC:
        return "overall value, balancing score and price"

    if query.sort_by == SortBy.NAME_ASC:
        return "name in alphabetical order"

    if query.sort_by == SortBy.VINTAGE_DESC:
        return "newest vintage first"

    if query.sort_by == SortBy.RELEVANCE:
        return "relevance based on the active filters"

    return "the default ranking for this query"


def _build_success_summary(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> str:
    """
    Build the main answer summary for successful matches.
    """
    total_matches = retrieval_result["total_matches"]
    returned_count = retrieval_result["returned_count"]
    page = retrieval_result.get("page", 1)
    total_pages = retrieval_result.get("total_pages", 1)

    filters_text = _describe_filters(query)
    ranking_text = _describe_ranking(query)

    if total_pages > 1:
        page_text = f" I am showing page {page} of {total_pages}."
    else:
        page_text = ""

    return (
        f"I found {total_matches} matching {_pluralize('wine', total_matches)} "
        f"{filters_text} and ranked them by {ranking_text}. "
        f"Here {'is' if returned_count == 1 else 'are'} the {returned_count} on this page."
        f"{page_text}"
    )


def _build_soft_refinement_summary(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> str:
    """
    Build a summary for broad queries where we still show page 1 results.
    """
    total_matches = retrieval_result["total_matches"]
    returned_count = retrieval_result["returned_count"]
    page = retrieval_result.get("page", 1)
    total_pages = retrieval_result.get("total_pages", 1)
    filters_text = _describe_filters(query)
    ranking_text = _describe_ranking(query)

    return (
        f"I found {total_matches} matching {_pluralize('wine', total_matches)} "
        f"{filters_text} and ranked them by {ranking_text}. "
        f"I am showing {returned_count} on page {page} of {total_pages}. "
        f"You can narrow the search further with budget, color, country, region, producer, or varietal."
    )


def _build_zero_results_summary(query: StructuredWineQuery) -> str:
    """
    Build a clear zero-results response without inventing alternatives.
    """
    filters_text = _describe_filters(query)

    if filters_text == "from the collection":
        return "I could not find any matching wines. Try widening the budget or removing one filter."

    return (
        f"I could not find any matching wines {filters_text}. "
        f"Try widening the budget or removing one filter."
    )


def _build_short_spoken_summary(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> str:
    """
    Build a shorter version of the answer for text-to-speech.
    """
    total_matches = retrieval_result["total_matches"]
    returned_count = retrieval_result["returned_count"]

    if total_matches == 0:
        return "I could not find any matching wines."

    if retrieval_result.get("needs_refinement"):
        page = retrieval_result.get("page", 1)
        return f"I found {total_matches} matches. I am showing page {page}. You can narrow it further."

    if query.intent == QueryIntent.CHEAPEST:
        return f"I found {total_matches} matches. Here are the cheapest {returned_count}."

    if query.intent == QueryIntent.MOST_EXPENSIVE:
        return f"I found {total_matches} matches. Here are the most expensive {returned_count}."

    if query.intent == QueryIntent.BEST_RATED_UNDER_BUDGET:
        return f"I found {total_matches} matches. Here are the top rated {returned_count}."

    if query.intent == QueryIntent.GIFT_RECOMMENDATION:
        return f"I found {total_matches} good gift options. Here are the top {returned_count}."

    return f"I found {total_matches} matches. Here are the top {returned_count}."


def _build_unresolved_entity_summary(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> str:
    """
    Build a grounded response when the user explicitly asked for an entity
    that does not exist in the dataset.
    """
    raw_message = retrieval_result.get("message")
    if raw_message:
        return raw_message

    if not query.unresolved_entities:
        return "I could not match one or more requested entities in the current dataset."

    first_entity = query.unresolved_entities[0]
    if first_entity.reason == UnresolvedReason.FIELD_MISSING_FROM_DATASET:
        return (
            f"The current dataset does not include {first_entity.value} information. "
            f"Try filtering by country, color, producer, varietal, budget, or score instead."
        )

    if first_entity.closest_matches:
        matches_text = ", ".join(first_entity.closest_matches[:3])
        return f"I could not match '{first_entity.value}' in the current dataset. Closest grounded options are {matches_text}."

    return f"I could not match '{first_entity.value}' in the current dataset."


def _build_unresolved_entity_spoken_summary(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> str:
    """
    Spoken version of the unresolved-entity message.
    """
    raw_message = retrieval_result.get("message")
    if raw_message:
        return raw_message

    if not query.unresolved_entities:
        return "I could not match one or more requested entities."

    first_entity = query.unresolved_entities[0]
    if first_entity.reason == UnresolvedReason.FIELD_MISSING_FROM_DATASET:
        return f"The current dataset does not include {first_entity.value} information."

    return f"I could not match {first_entity.value} in the current dataset."


def _build_followup_suggestions(
    query: StructuredWineQuery,
    retrieval_result: dict[str, Any],
    response_type: str,
) -> list[dict[str, str]]:
    if response_type == "clarification":
        suggestions = _build_clarification_suggestions(query)
        return _filter_suggestions_for_query(query, _dedupe_suggestions(suggestions))

    if query.unresolved_entities and retrieval_result.get("total_matches", 0) == 0:
        suggestions = _build_unresolved_suggestions(query)
        return _filter_suggestions_for_query(query, _dedupe_suggestions(suggestions))

    if retrieval_result.get("needs_refinement"):
        suggestions = _build_refinement_suggestions()
        return _filter_suggestions_for_query(query, _dedupe_suggestions(suggestions))

    if response_type == "no_results":
        suggestions = _build_no_results_suggestions()
        return _filter_suggestions_for_query(query, _dedupe_suggestions(suggestions))

    return []


def build_response(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> dict[str, Any]:
    """
    Build the final response payload.
    """
    total_matches = retrieval_result.get("total_matches", 0)
    returned_count = retrieval_result.get("returned_count", 0)
    raw_message = retrieval_result.get("message")

    if query.intent == QueryIntent.UNSUPPORTED_REQUEST:
        summary = raw_message or "This request is not supported by the current dataset."
        spoken_summary = summary
        response_type = "unsupported"

    elif query.needs_clarification:
        summary = raw_message or "I need one more detail before I can search the collection."
        spoken_summary = summary
        response_type = "clarification"

    elif query.unresolved_entities and total_matches == 0:
        summary = _build_unresolved_entity_summary(query, retrieval_result)
        spoken_summary = _build_unresolved_entity_spoken_summary(query, retrieval_result)
        response_type = "no_results"

    elif total_matches == 0:
        summary = _build_zero_results_summary(query)
        spoken_summary = _build_short_spoken_summary(query, retrieval_result)
        response_type = "no_results"

    else:
        if retrieval_result.get("needs_refinement"):
            summary = _build_soft_refinement_summary(query, retrieval_result)
        else:
            summary = _build_success_summary(query, retrieval_result)

        spoken_summary = _build_short_spoken_summary(query, retrieval_result)
        response_type = "results"

    followup_suggestions = _build_followup_suggestions(query, retrieval_result, response_type)

    return {
        **retrieval_result,
        "response_type": response_type,
        "summary": summary,
        "spoken_summary": spoken_summary,
        "applied_filters_text": _describe_filters(query),
        "ranking_basis_text": _describe_ranking(query),
        "show_results": returned_count > 0,
        "followup_suggestions": followup_suggestions,
    }
