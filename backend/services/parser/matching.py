from __future__ import annotations

import re

from backend.core.dataset_metadata import get_dataset_metadata
from backend.core.schemas import QueryFilters, UnresolvedEntity
from backend.utils.helpers import best_value_match, normalize_text


# Words that usually mark the end of a location phrase in the query.
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

# Generic phrases that should not become unresolved entities.
_LOCATION_IGNORE_VALUES = {
    "wine",
    "wines",
    "the collection",
    "collection",
    "stock",
    "inventory",
}


def _extract_explicit_location_phrase(question: str) -> str | None:
    """
    Extract a simple explicit location phrase from the user's question.

    Examples:
    - "best red wine in India" -> "India"
    - "show me wines from India under $20" -> "India"

    This is intentionally narrow for Phase 2. We only want to capture the
    most obvious explicit location constraints first.
    """
    escaped_boundaries = "|".join(re.escape(word) for word in _LOCATION_BOUNDARY_WORDS)

    pattern = (
        rf"\b(?:from|in)\s+"
        rf"([a-zA-Z][a-zA-Z\s'&.\-]{{1,40}}?)"
        rf"(?=\s+(?:{escaped_boundaries})\b|$)"
    )

    match = re.search(pattern, question, flags=re.IGNORECASE)
    if not match:
        return None

    candidate = " ".join(match.group(1).strip().split())
    return candidate or None


def _candidate_matches_existing_filters(candidate: str, filters: QueryFilters) -> bool:
    """
    Return True if the extracted phrase already matched some known field.

    This prevents false unresolved hits for queries like:
    - "Find wines from Stag's Leap Wine Cellars under 100"

    where "from X" is actually a producer phrase, not a country/region.
    """
    normalized_candidate = normalize_text(candidate)

    for value in [
        filters.country,
        filters.region,
        filters.appellation,
        filters.producer,
        filters.varietal,
        filters.name,
    ]:
        if value and normalize_text(str(value)) == normalized_candidate:
            return True

    return False


def _build_unresolved_location_entity(candidate: str) -> UnresolvedEntity | None:
    """
    Turn an unmatched explicit location phrase into an unresolved entity.
    """
    cleaned_value = " ".join(candidate.strip().split())
    normalized_value = normalize_text(cleaned_value)

    if not cleaned_value:
        return None

    if normalized_value in _LOCATION_IGNORE_VALUES:
        return None

    # Ignore extremely short fragments that are likely noise.
    if len(normalized_value) < 3:
        return None

    return UnresolvedEntity(
        field="country_or_region",
        value=cleaned_value,
        phrase=cleaned_value,
    )


def apply_dataset_matches(
    question: str,
    filters: QueryFilters,
) -> tuple[QueryFilters, list[float], list[UnresolvedEntity]]:
    """
    Fill country / region / appellation / producer / varietal / name
    from dataset metadata.

    In Phase 2, this function also detects explicit location-style phrases
    that did not match the dataset and returns them as unresolved entities.
    """
    metadata = get_dataset_metadata()
    scores: list[float] = []
    unresolved_entities: list[UnresolvedEntity] = []

    normalized_question = normalize_text(question)

    country_values = metadata.field_indexes["country"].values
    region_values = metadata.field_indexes["region"].values
    appellation_values = metadata.field_indexes["appellation"].values
    producer_values = metadata.field_indexes["producer"].values
    varietal_values = metadata.field_indexes["varietal"].values
    name_values = metadata.field_indexes["name"].values

    # Country matching
    country_match = best_value_match(question, country_values, score_cutoff=93, allow_fuzzy=True)
    if country_match:
        filters.country = country_match[0]
        scores.append(country_match[1] / 100)

    # Region matching
    region_match = best_value_match(question, region_values, score_cutoff=91, allow_fuzzy=True)
    if region_match:
        filters.region = region_match[0]
        scores.append(region_match[1] / 100)

    # Appellation matching
    appellation_match = best_value_match(question, appellation_values, score_cutoff=91, allow_fuzzy=True)
    if appellation_match:
        filters.appellation = appellation_match[0]
        scores.append(appellation_match[1] / 100)

    # Producer matching
    producer_match = best_value_match(question, producer_values, score_cutoff=93, allow_fuzzy=True)
    if producer_match:
        filters.producer = producer_match[0]
        scores.append(producer_match[1] / 100)

    # Varietal matching
    varietal_match = best_value_match(question, varietal_values, score_cutoff=92, allow_fuzzy=True)
    if varietal_match:
        filters.varietal = varietal_match[0]
        scores.append(varietal_match[1] / 100)

    # Name matching stays stricter to avoid noisy false positives.
    if re.search(r"\b(named|called)\b", normalized_question):
        name_match = best_value_match(question, name_values, score_cutoff=96, allow_fuzzy=False)
        if name_match:
            filters.name = name_match[0]
            scores.append(name_match[1] / 100)

    # Prevent the same text from being applied as both region and appellation.
    if filters.region and filters.appellation:
        if normalize_text(filters.region) == normalize_text(filters.appellation):
            if "appellation" in normalized_question or "ava" in normalized_question:
                filters.region = None
            else:
                filters.appellation = None

    # Phase 2: detect explicit location-style phrases that did not match
    # country / region / appellation and were not already matched elsewhere.
    explicit_location = _extract_explicit_location_phrase(question)
    if explicit_location:
        matched_geography = any([filters.country, filters.region, filters.appellation])
        already_matched_elsewhere = _candidate_matches_existing_filters(explicit_location, filters)

        if not matched_geography and not already_matched_elsewhere:
            unresolved_entity = _build_unresolved_location_entity(explicit_location)
            if unresolved_entity is not None:
                unresolved_entities.append(unresolved_entity)

    return filters, scores, unresolved_entities