from __future__ import annotations

import re

from backend.core.dataset_metadata import get_dataset_metadata
from backend.core.schemas import QueryFilters, UnresolvedEntity
from backend.utils.helpers import best_value_match, exact_phrase_match, normalize_text


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

# Generic phrases that should never become unresolved entities.
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
    Extract a simple explicit phrase following "from" or "in".

    Examples:
    - "best red wine in India" -> "India"
    - "show me wines from France under $20" -> "France"
    - "Find wines from Stag's Leap Wine Cellars under $100" -> "Stag's Leap Wine Cellars"

    Phase 2 keeps this intentionally narrow and only handles obvious
    location-style phrases first.
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

    candidate = " ".join(match.group(1).strip().split())
    return candidate or None


def _candidate_matches_existing_filters(candidate: str, filters: QueryFilters) -> bool:
    """
    Return True if the candidate already matched some known filter.

    This prevents false unresolved hits for prompts like:
    - "Find wines from Stag's Leap Wine Cellars under 100"

    where "from X" is really a producer phrase, not a country/region.
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

    # Ignore very short fragments that are likely just noise.
    if len(normalized_value) < 3:
        return None

    return UnresolvedEntity(
        field="country_or_region",
        value=cleaned_value,
        phrase=cleaned_value,
    )


def _resolve_explicit_location_phrase(
    location_phrase: str,
    country_values: list[str],
    region_values: list[str],
    appellation_values: list[str],
) -> tuple[str | None, str | None, str | None, float | None]:
    """
    Resolve one explicit location phrase with strict precedence:
    country -> region -> appellation.

    Important:
    - Prefer exact phrase matches first.
    - Allow fuzzy matching as a fallback, but only for the single extracted
      location phrase, not the whole question.
    - Stop after the first successful geography match so one phrase does not
      populate multiple geography fields.
    """
    # Country first
    country_match = exact_phrase_match(location_phrase, country_values)
    if country_match is None:
        country_match = best_value_match(location_phrase, country_values, score_cutoff=93, allow_fuzzy=True)
    if country_match:
        return country_match[0], None, None, country_match[1] / 100

    # Region second
    region_match = exact_phrase_match(location_phrase, region_values)
    if region_match is None:
        region_match = best_value_match(location_phrase, region_values, score_cutoff=93, allow_fuzzy=True)
    if region_match:
        return None, region_match[0], None, region_match[1] / 100

    # Appellation third
    appellation_match = exact_phrase_match(location_phrase, appellation_values)
    if appellation_match is None:
        appellation_match = best_value_match(location_phrase, appellation_values, score_cutoff=93, allow_fuzzy=True)
    if appellation_match:
        return None, None, appellation_match[0], appellation_match[1] / 100

    return None, None, None, None


def apply_dataset_matches(
    question: str,
    filters: QueryFilters,
) -> tuple[QueryFilters, list[float], list[UnresolvedEntity]]:
    """
    Fill country / region / appellation / producer / varietal / name
    from dataset metadata.

    Phase 2 behavior:
    - explicit location phrases like "from France" or "in India" are handled
      separately and more strictly than general fuzzy matching
    - unresolved explicit location phrases are preserved instead of silently
      disappearing
    - producer phrases like "from Stag's Leap Wine Cellars" are allowed to
      match producer first, so they are not incorrectly treated as geography
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

    # ---------------------------------------------------------------------
    # 1. Extract the explicit phrase after "from" or "in" once.
    # ---------------------------------------------------------------------
    explicit_location = _extract_explicit_location_phrase(question)

    # ---------------------------------------------------------------------
    # 2. Geography: if an explicit location phrase exists, resolve it first
    #    as country -> region -> appellation.
    # ---------------------------------------------------------------------
    if explicit_location:
        matched_country, matched_region, matched_appellation, match_score = _resolve_explicit_location_phrase(
            explicit_location,
            country_values,
            region_values,
            appellation_values,
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

    # ---------------------------------------------------------------------
    # 3. Non-geographic matching across the full question.
    #    This must happen before unresolved-entity fallback so producer phrases
    #    like "from Stag's Leap Wine Cellars" get claimed properly.
    # ---------------------------------------------------------------------

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

    # Wine name matching stays stricter because it is noisy.
    if re.search(r"\b(named|called)\b", normalized_question):
        name_match = best_value_match(question, name_values, score_cutoff=96, allow_fuzzy=False)
        if name_match:
            filters.name = name_match[0]
            scores.append(name_match[1] / 100)

    # ---------------------------------------------------------------------
    # 4. If the explicit phrase did not resolve as geography and it was not
    #    matched as producer/name/varietal, treat it as unresolved.
    # ---------------------------------------------------------------------
    if explicit_location:
        matched_geography = any([filters.country, filters.region, filters.appellation])
        already_matched_elsewhere = _candidate_matches_existing_filters(explicit_location, filters)

        if not matched_geography and not already_matched_elsewhere:
            unresolved_entity = _build_unresolved_location_entity(explicit_location)
            if unresolved_entity is not None:
                unresolved_entities.append(unresolved_entity)

    # ---------------------------------------------------------------------
    # 5. Optional fallback geography matching only when there was no explicit
    #    location phrase. This keeps broad geography matching available without
    #    letting "France" also become "Southwest France".
    # ---------------------------------------------------------------------
    if not explicit_location and not filters.country:
        country_match = best_value_match(question, country_values, score_cutoff=93, allow_fuzzy=True)
        if country_match:
            filters.country = country_match[0]
            scores.append(country_match[1] / 100)

    if not explicit_location and not filters.region and not filters.country:
        region_match = best_value_match(question, region_values, score_cutoff=91, allow_fuzzy=True)
        if region_match:
            filters.region = region_match[0]
            scores.append(region_match[1] / 100)

    if not explicit_location and not filters.appellation and not filters.region and not filters.country:
        appellation_match = best_value_match(question, appellation_values, score_cutoff=91, allow_fuzzy=True)
        if appellation_match:
            filters.appellation = appellation_match[0]
            scores.append(appellation_match[1] / 100)

    # Prevent the same text from being used as both region and appellation.
    if filters.region and filters.appellation:
        if normalize_text(filters.region) == normalize_text(filters.appellation):
            if "appellation" in normalized_question or "ava" in normalized_question:
                filters.region = None
            else:
                filters.appellation = None

    return filters, scores, unresolved_entities