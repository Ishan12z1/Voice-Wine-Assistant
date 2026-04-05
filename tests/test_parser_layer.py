from __future__ import annotations

from backend.services.parser.parser import parse_query


def test_parser_tracks_invalid_explicit_location() -> None:
    query = parse_query("best red wine in India")

    assert query.filters.color == "red" or str(query.filters.color) == "WineColor.RED"
    assert query.filters.country is None
    assert query.filters.region is None
    assert query.filters.appellation is None
    assert len(query.unresolved_entities) == 1
    assert query.unresolved_entities[0].field == "country_or_region"
    assert query.unresolved_entities[0].reason == "not_in_dataset"


def test_parser_does_not_confuse_producer_with_location() -> None:
    query = parse_query("Find wines from Stag's Leap Wine Cellars under $100")

    assert query.filters.producer == "Stag's Leap Wine Cellars"
    assert query.unresolved_entities == []


def test_parser_marks_missing_dataset_capability() -> None:
    query = parse_query("show me dry red wines")

    assert len(query.unresolved_entities) >= 1
    assert query.unresolved_entities[0].field == "sweetness"
    assert query.unresolved_entities[0].reason == "field_missing_from_dataset"
    assert query.unresolved_entities[0].dataset_has_field is False


def test_parser_requires_budget_for_recommendation_flow() -> None:
    query = parse_query("Recommend a housewarming gift")

    assert query.needs_clarification is True
    assert query.missing_fields == ["budget"]
    assert query.occasion == "housewarming"


def test_parser_requires_varietal_before_color_for_grape_request() -> None:
    query = parse_query("Recommend a wine by grape under $30")

    assert query.needs_clarification is True
    assert query.missing_fields == ["varietal"]
    assert query.filters.max_price == 30.0
    assert query.filters.require_varietal is True


def test_parser_blocks_general_education_requests() -> None:
    query = parse_query("Teach me how tannins work")

    assert query.intent == "unsupported_request"
    assert query.unsupported_reason is not None


def test_parser_keeps_non_price_numeric_signals_distinct() -> None:
    query = parse_query("show me wines with abv above 14%")

    assert query.filters.min_abv == 14.0
    assert query.filters.min_price is None
    assert query.filters.max_price is None


def test_parser_does_not_misread_price_range_as_abv_range() -> None:
    query = parse_query("red wine between 30 and 60 dollar")

    assert query.filters.color == "red" or str(query.filters.color) == "WineColor.RED"
    assert query.filters.min_price == 30.0
    assert query.filters.max_price == 60.0
    assert query.filters.min_abv is None
    assert query.filters.max_abv is None
