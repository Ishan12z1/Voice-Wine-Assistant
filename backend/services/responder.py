"""
responder.py

This file builds short, grounded natural-language responses from the retrieval
output. It does not search the dataset and it does not rank wines.
"""

from __future__ import annotations

from typing import Any

from backend.core.schemas import QueryIntent, SortBy, StructuredWineQuery


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

    filters_text = _describe_filters(query)
    ranking_text = _describe_ranking(query)

    return (
        f"I found {total_matches} matching {_pluralize('wine', total_matches)} "
        f"{filters_text} and ranked them by {ranking_text}. "
        f"Here {'is' if returned_count == 1 else 'are'} the top {returned_count}."
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

    if query.intent == QueryIntent.CHEAPEST:
        return f"I found {total_matches} matches. Here are the cheapest {returned_count}."

    if query.intent == QueryIntent.MOST_EXPENSIVE:
        return f"I found {total_matches} matches. Here are the most expensive {returned_count}."

    if query.intent == QueryIntent.BEST_RATED_UNDER_BUDGET:
        return f"I found {total_matches} matches. Here are the top rated {returned_count}."

    if query.intent == QueryIntent.GIFT_RECOMMENDATION:
        return f"I found {total_matches} good gift options. Here are the top {returned_count}."

    return f"I found {total_matches} matches. Here are the top {returned_count}."


def _build_refinement_summary(retrieval_result: dict[str, Any]) -> str:
    """
    Build the refinement summary for broad result sets.

    Current behavior still hides results for refinement cases.
    Soft refinement with page 1 results comes later in V2.
    """
    total_matches = retrieval_result["total_matches"]
    return (
        f"I found {total_matches} matching wines, which is too broad to show usefully. "
        f"Please add one more filter like budget, color, country, region, producer, or varietal."
    )


def _build_refinement_spoken_summary(retrieval_result: dict[str, Any]) -> str:
    """
    Short spoken version of the refinement message.
    """
    total_matches = retrieval_result["total_matches"]
    return f"I found {total_matches} matches. Please add another filter."


def _build_unresolved_entity_summary(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> str:
    """
    Build a grounded response when the user explicitly asked for an entity
    that does not exist in the dataset.

    Example:
    - "best red wine in India"
    """
    raw_message = retrieval_result.get("message")
    if raw_message:
        return raw_message

    if not query.unresolved_entities:
        return "I could not match one or more requested entities in the current dataset."

    first_entity = query.unresolved_entities[0]
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
    return f"I could not match {first_entity.value} in the current dataset."


def build_response(query: StructuredWineQuery, retrieval_result: dict[str, Any]) -> dict[str, Any]:
    """
    Build the final response payload.

    This function does not alter the wine list itself. It only adds grounded
    response text around the retrieval result.
    """
    total_matches = retrieval_result.get("total_matches", 0)
    returned_count = retrieval_result.get("returned_count", 0)
    raw_message = retrieval_result.get("message")

    # Case 1: Unsupported request
    if query.intent == QueryIntent.UNSUPPORTED_REQUEST:
        summary = raw_message or "This request is not supported by the current dataset."
        spoken_summary = summary
        response_type = "unsupported"

    # Case 2: Ambiguous / clarification needed
    elif query.needs_clarification:
        summary = raw_message or "I need one more detail before I can search the collection."
        spoken_summary = summary
        response_type = "clarification"

    # Case 3: Explicit unresolved entity from the parser
    elif query.unresolved_entities and total_matches == 0:
        summary = _build_unresolved_entity_summary(query, retrieval_result)
        spoken_summary = _build_unresolved_entity_spoken_summary(query, retrieval_result)
        response_type = "no_results"

    # Case 4: Refinement
    elif retrieval_result.get("needs_refinement"):
        summary = _build_refinement_summary(retrieval_result)
        spoken_summary = _build_refinement_spoken_summary(retrieval_result)
        response_type = "too_many_matches"

    # Case 5: Zero results
    elif total_matches == 0:
        summary = _build_zero_results_summary(query)
        spoken_summary = _build_short_spoken_summary(query, retrieval_result)
        response_type = "no_results"

    # Case 6: Successful retrieval
    else:
        summary = _build_success_summary(query, retrieval_result)
        spoken_summary = _build_short_spoken_summary(query, retrieval_result)
        response_type = "results"

    return {
        **retrieval_result,
        "response_type": response_type,
        "summary": summary,
        "spoken_summary": spoken_summary,
        "applied_filters_text": _describe_filters(query),
        "ranking_basis_text": _describe_ranking(query),
        "show_results": response_type == "results" and returned_count > 0,
    }