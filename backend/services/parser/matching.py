from __future__ import annotations

import re

from backend.core.dataset_metadata import get_dataset_metadata
from backend.core.schemas import QueryFilters
from backend.utils.helpers import best_value_match, normalize_text


def apply_dataset_matches(question: str, filters: QueryFilters) -> tuple[QueryFilters, list[float]]:
    """
    Fill country / region / appellation / producer / varietal / name
    from dataset metadata.

    This is the matching layer only. It does not decide final intent or
    clarification behavior.
    """
    metadata = get_dataset_metadata()
    scores: list[float] = []
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

    return filters, scores