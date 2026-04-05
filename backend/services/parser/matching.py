from __future__ import annotations

import re

from backend.core.dataset_metadata import (
    get_top_field_values,
    resolve_field_value,
)
from backend.core.schemas import QueryFilters, UnresolvedEntity, UnresolvedReason, WineColor
from backend.utils.helpers import normalize_text


_LOCATION_BOUNDARY_WORDS = [
    "under",
    "below",
    "over",
    "above",
    "with",
    "that",
    "between",
    "priced",
    "score",
    "rated",
    "rating",
    "abv",
    "vintage",
    "bottle",
    "bottles",
    "gift",
    "for",
]

_PHRASE_IGNORE_VALUES = {
    "wine",
    "wines",
    "the collection",
    "collection",
    "stock",
    "inventory",
}

_PRODUCER_HINT_WORDS = [
    "cellars",
    "cellar",
    "vineyards",
    "vineyard",
    "winery",
    "estate",
    "chateau",
    "domaine",
    "domaines",
]


def _clean_phrase(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _extract_explicit_location_phrase(question: str) -> str | None:
    """
    Extract a simple phrase following "from" or "in".
    """
    escaped_boundaries = "|".join(re.escape(word) for word in _LOCATION_BOUNDARY_WORDS)

    pattern = (
        rf"\b(?:from|in)\s+"
        rf"([a-zA-Z][a-zA-Z\s'&.\-]{{1,60}}?)"
        rf"(?=\s+(?:{escaped_boundaries})\b|$)"
    )

    match = re.search(pattern, question, flags=re.IGNORECASE)
    if not match:
        return None

    return _clean_phrase(match.group(1))


def _extract_value_after_keywords(question: str, keywords: list[str]) -> str | None:
    """
    Extract a short phrase after a keyword like "called" or "grape".
    """
    escaped_keywords = "|".join(re.escape(keyword) for keyword in keywords)
    escaped_boundaries = "|".join(re.escape(word) for word in _LOCATION_BOUNDARY_WORDS)

    pattern = (
        rf"\b(?:{escaped_keywords})\s+"
        rf"([a-zA-Z][a-zA-Z0-9\s'&.\-]{{1,60}}?)"
        rf"(?=\s+(?:{escaped_boundaries})\b|$)"
    )

    match = re.search(pattern, question, flags=re.IGNORECASE)
    if not match:
        return None

    return _clean_phrase(match.group(1))


def _looks_like_producer_phrase(candidate: str) -> bool:
    normalized = normalize_text(candidate)
    return any(hint in normalized for hint in _PRODUCER_HINT_WORDS)


def _candidate_matches_existing_filters(candidate: str, filters: QueryFilters) -> bool:
    normalized_candidate = normalize_text(candidate)

    for value in [
        filters.country,
        filters.region,
        filters.appellation,
        filters.producer,
        filters.varietal,
        filters.name,
        filters.color,
    ]:
        if value and normalize_text(str(value)) == normalized_candidate:
            return True

    return False


def _append_unresolved_entity(
    unresolved_entities: list[UnresolvedEntity],
    entity: UnresolvedEntity | None,
) -> None:
    if entity is None:
        return

    normalized_value = normalize_text(entity.value)
    for existing in unresolved_entities:
        if existing.field == entity.field and normalize_text(existing.value) == normalized_value:
            return

    unresolved_entities.append(entity)


def _build_unresolved_entity(
    field: str,
    value: str,
    *,
    phrase: str | None = None,
    reason: UnresolvedReason = UnresolvedReason.NOT_IN_DATASET,
    dataset_has_field: bool = True,
    closest_matches: list[str] | None = None,
) -> UnresolvedEntity | None:
    cleaned_value = _clean_phrase(value)
    if cleaned_value is None:
        return None

    normalized_value = normalize_text(cleaned_value)
    if normalized_value in _PHRASE_IGNORE_VALUES or len(normalized_value) < 3:
        return None

    return UnresolvedEntity(
        field=field,
        value=cleaned_value,
        phrase=_clean_phrase(phrase) or cleaned_value,
        reason=reason,
        dataset_has_field=dataset_has_field,
        closest_matches=closest_matches or [],
    )


def _resolve_geography_phrase(location_phrase: str) -> tuple[str | None, str | None, str | None, float | None]:
    """
    Resolve one explicit phrase with strict geography precedence.
    """
    country_match, country_score, _ = resolve_field_value("country", location_phrase)
    if country_match:
        return country_match, None, None, (country_score or 100.0) / 100

    region_match, region_score, _ = resolve_field_value("region", location_phrase)
    if region_match:
        return None, region_match, None, (region_score or 100.0) / 100

    appellation_match, appellation_score, _ = resolve_field_value("appellation", location_phrase)
    if appellation_match:
        return None, None, appellation_match, (appellation_score or 100.0) / 100

    return None, None, None, None


def _apply_field_match(
    question: str,
    field_name: str,
) -> tuple[str | None, float | None, list[str]]:
    matched_value, match_score, suggestions = resolve_field_value(field_name, question)
    if matched_value is None:
        return None, None, suggestions
    return matched_value, (match_score or 100.0) / 100, []


def _coerce_color(value: str | None) -> WineColor | None:
    if value is None:
        return None

    try:
        return WineColor(value)
    except ValueError:
        return None


def apply_dataset_matches(
    question: str,
    filters: QueryFilters,
) -> tuple[QueryFilters, list[float], list[UnresolvedEntity]]:
    """
    Ground supported text fields against dataset metadata.
    """
    scores: list[float] = []
    unresolved_entities: list[UnresolvedEntity] = []
    normalized_question = normalize_text(question)

    explicit_location = _extract_explicit_location_phrase(question)

    if explicit_location:
        matched_country, matched_region, matched_appellation, match_score = _resolve_geography_phrase(
            explicit_location
        )

        if matched_country:
            filters.country = matched_country
            scores.append(match_score or 1.0)
        elif matched_region:
            filters.region = matched_region
            scores.append(match_score or 1.0)
        elif matched_appellation:
            filters.appellation = matched_appellation
            scores.append(match_score or 1.0)
        else:
            producer_match, producer_score, producer_suggestions = _apply_field_match(explicit_location, "producer")
            if producer_match:
                filters.producer = producer_match
                scores.append(producer_score or 1.0)
            else:
                unresolved_field = "producer" if _looks_like_producer_phrase(explicit_location) else "country_or_region"
                suggestions = (
                    producer_suggestions
                    if unresolved_field == "producer"
                    else get_top_field_values("country", limit=3)
                )
                _append_unresolved_entity(
                    unresolved_entities,
                    _build_unresolved_entity(
                        unresolved_field,
                        explicit_location,
                        phrase=explicit_location,
                        closest_matches=suggestions,
                    ),
                )

    if filters.color is None:
        color_match, color_score, _ = _apply_field_match(question, "color")
        color = _coerce_color(color_match)
        if color is not None:
            filters.color = color
            scores.append(color_score or 1.0)

    if filters.producer is None:
        producer_match, producer_score, _ = _apply_field_match(question, "producer")
        if producer_match:
            filters.producer = producer_match
            scores.append(producer_score or 1.0)

    if filters.varietal is None:
        varietal_match, varietal_score, _ = _apply_field_match(question, "varietal")
        if varietal_match:
            filters.varietal = varietal_match
            scores.append(varietal_score or 1.0)

    if not explicit_location and filters.country is None:
        country_match, country_score, _ = _apply_field_match(question, "country")
        if country_match:
            filters.country = country_match
            scores.append(country_score or 1.0)

    if not explicit_location and filters.region is None and filters.country is None:
        region_match, region_score, _ = _apply_field_match(question, "region")
        if region_match:
            filters.region = region_match
            scores.append(region_score or 1.0)

    if not explicit_location and filters.appellation is None and filters.region is None and filters.country is None:
        appellation_match, appellation_score, _ = _apply_field_match(question, "appellation")
        if appellation_match:
            filters.appellation = appellation_match
            scores.append(appellation_score or 1.0)

    if re.search(r"\b(named|called)\b", normalized_question) and filters.name is None:
        name_match, name_score, name_suggestions = _apply_field_match(question, "name")
        if name_match:
            filters.name = name_match
            scores.append(name_score or 1.0)
        else:
            candidate_name = _extract_value_after_keywords(question, ["named", "called"])
            _append_unresolved_entity(
                unresolved_entities,
                _build_unresolved_entity(
                    "name",
                    candidate_name or question,
                    phrase=candidate_name,
                    closest_matches=name_suggestions or get_top_field_values("name", limit=3),
                ),
            )

    if re.search(r"\b(varietal|grape|grapes)\b", normalized_question) and filters.varietal is None:
        candidate_varietal = _extract_value_after_keywords(
            question,
            ["varietal", "grape", "grapes", "made from", "made with"],
        )
        if candidate_varietal and not _candidate_matches_existing_filters(candidate_varietal, filters):
            _append_unresolved_entity(
                unresolved_entities,
                _build_unresolved_entity(
                    "varietal",
                    candidate_varietal,
                    phrase=candidate_varietal,
                    closest_matches=resolve_field_value("varietal", candidate_varietal)[2]
                    or get_top_field_values("varietal", limit=3),
                ),
            )

    if re.search(r"\b(?:producer|winery|vineyard|estate)\b", normalized_question) and filters.producer is None:
        candidate_producer = _extract_value_after_keywords(
            question,
            ["producer", "winery", "vineyard", "estate"],
        )
        if candidate_producer and not _candidate_matches_existing_filters(candidate_producer, filters):
            _append_unresolved_entity(
                unresolved_entities,
                _build_unresolved_entity(
                    "producer",
                    candidate_producer,
                    phrase=candidate_producer,
                    closest_matches=resolve_field_value("producer", candidate_producer)[2]
                    or get_top_field_values("producer", limit=3),
                ),
            )

    if filters.region and filters.appellation:
        if normalize_text(filters.region) == normalize_text(filters.appellation):
            if "appellation" in normalized_question or "ava" in normalized_question:
                filters.region = None
            else:
                filters.appellation = None

    return filters, scores, unresolved_entities
