from __future__ import annotations

import re

from backend.core.schemas import Occasion, QueryFilters, SortBy, WineColor
from backend.utils.helpers import (
    has_any_phrase,
    liters_to_ml,
    normalize_text,
    safe_float,
    safe_int,
)


# Out-of-scope education / invented-knowledge style requests.
UNSUPPORTED_PATTERNS: list[tuple[str, str]] = [
    (r"\bteach me\b", "This app does not teach general wine concepts."),
    (r"\bexplain (tannins?|acidity|body|terroir|wine)\b", "This app does not handle general wine education."),
    (r"\btannin\b|\btannins\b", "This app does not answer wine education questions."),
    (r"\bfood pairing\b|\bpair with\b|\bpairs with\b", "Food pairing is not supported unless that data exists."),
    (r"\btasting note\b|\btasting notes\b|\bflavor profile\b", "Invented tasting notes are out of scope."),
    (r"\bwinery history\b|\bhistory of\b", "Winery history is outside the dataset-backed scope."),
    (r"\bwhat does .* taste like\b", "Taste descriptions are not supported unless present in the data."),
]

# Generic browse phrases that make broad queries still usable.
BROWSE_KEYWORDS = [
    "show me",
    "find",
    "browse",
    "list",
    "what do you have",
    "what wines do you have",
    "give me",
]

DATASET_CAPABILITY_PATTERNS: dict[str, dict[str, list[str] | str]] = {
    "sweetness": {
        "label": "sweetness",
        "phrases": ["sweetness", "dry", "off dry", "semi sweet", "sweet wine"],
    },
    "food_pairing": {
        "label": "food pairing",
        "phrases": ["food pairing", "pair with", "pairs with", "pairing"],
    },
    "tasting_notes": {
        "label": "tasting notes",
        "phrases": ["tasting note", "tasting notes", "flavor profile", "aroma", "aromas"],
    },
}


def detect_dataset_capability_gaps(question: str) -> list[tuple[str, str]]:
    """
    Detect user requests for fields that the current dataset does not provide.
    """
    normalized_question = normalize_text(question)
    gaps: list[tuple[str, str]] = []

    for field_name, config in DATASET_CAPABILITY_PATTERNS.items():
        phrases = [normalize_text(phrase) for phrase in config["phrases"]]
        if has_any_phrase(normalized_question, phrases):
            gaps.append((field_name, str(config["label"])))

    return gaps


def detect_unsupported_reason(question: str) -> str | None:
    """
    Detect requests that are clearly outside the supported product scope.
    """
    normalized_question = normalize_text(question)

    for pattern, reason in UNSUPPORTED_PATTERNS:
        if re.search(pattern, normalized_question):
            return reason

    return None


def extract_limit(question: str) -> int | None:
    """
    Extract user-requested result count like:
    - top 5
    - show me 10
    - list 12
    """
    normalized_question = normalize_text(question)

    match = re.search(
        r"\b(?:top|show|list|give)\s+(?:me\s+)?(\d{1,2})\b",
        normalized_question,
    )
    if match:
        return max(1, min(int(match.group(1)), 50))

    return None


def extract_price_filters(
    question: str,
    *,
    allow_lenient_price: bool = False,
) -> tuple[float | None, float | None, float | None]:
    """
    Extract price filters.

    Returns:
    - min_price
    - max_price
    - confidence contribution
    """
    normalized_question = normalize_text(question)
    number = r"(\d+(?:\.\d+)?)"

    # Explicit money context
    between_match = re.search(
        rf"\b(?:between|from)\s+\$?\s*{number}\s+(?:and|to)\s+\$?\s*{number}\s*(?:dollars?|bucks?)?\b",
        question.lower(),
    )
    if between_match and (
        "$" in between_match.group(0)
        or re.search(r"\b(dollars?|bucks?)\b", between_match.group(0))
    ):
        return safe_float(between_match.group(1)), safe_float(between_match.group(2)), 0.98

    under_match = re.search(
        rf"\b(?:under|below|less than|cheaper than|up to|max|maximum of)\s+\$?\s*{number}\s*(?:dollars?|bucks?)?\b",
        question.lower(),
    )
    if under_match and (
        "$" in under_match.group(0)
        or re.search(r"\b(dollars?|bucks?)\b", under_match.group(0))
        or re.search(r"\b(price|budget|cost)\b", normalized_question)
    ):
        return None, safe_float(under_match.group(1)), 0.98

    over_match = re.search(
        rf"\b(?:over|above|more than|at least|min|minimum of)\s+\$?\s*{number}\s*(?:dollars?|bucks?)?\b",
        question.lower(),
    )
    if over_match and (
        "$" in over_match.group(0)
        or re.search(r"\b(dollars?|bucks?)\b", over_match.group(0))
        or re.search(r"\b(price|budget|cost)\b", normalized_question)
    ):
        return safe_float(over_match.group(1)), None, 0.98

    around_match = re.search(
        rf"\b(?:around|about)\s+\$?\s*{number}\s*(?:dollars?|bucks?)?\b",
        question.lower(),
    )
    if around_match and (
        "$" in around_match.group(0)
        or re.search(r"\b(dollars?|bucks?)\b", around_match.group(0))
        or re.search(r"\b(price|budget|cost)\b", normalized_question)
    ):
        center = safe_float(around_match.group(1))
        if center is not None:
            return max(center - 10, 0), center + 10, 0.75

    # Plain-number fallback only when no other numeric intent has claimed the number.
    if allow_lenient_price:
        under_plain_match = re.search(
            rf"\b(?:under|below|less than|cheaper than|up to|max|maximum of)\s+{number}\b",
            normalized_question,
        )
        if under_plain_match:
            return None, safe_float(under_plain_match.group(1)), 0.85

        over_plain_match = re.search(
            rf"\b(?:over|above|more than|at least|min|minimum of)\s+{number}\b",
            normalized_question,
        )
        if over_plain_match:
            return safe_float(over_plain_match.group(1)), None, 0.85

    return None, None, None


def extract_score_filters(question: str) -> tuple[float | None, float | None]:
    """
    Extract score-like filters such as:
    - score above 92
    - rated 95+
    """
    normalized_question = normalize_text(question)

    score_match = re.search(
        r"\b(?:score|rated|rating|ratings)\s+(?:above|over|at least|minimum of)?\s*(\d{2,3})\+?\b",
        normalized_question,
    )
    if score_match:
        score = safe_float(score_match.group(1))
        return score, 0.95

    score_plus_match = re.search(r"\b(\d{2,3})\+\b", normalized_question)
    if score_plus_match and "score" in normalized_question:
        score = safe_float(score_plus_match.group(1))
        return score, 0.9

    return None, None


def extract_vintage_filters(question: str) -> tuple[int | None, int | None, float | None]:
    """
    Extract vintage constraints.
    """
    normalized_question = normalize_text(question)

    between_match = re.search(
        r"\b(?:between|from)\s+(19\d{2}|20\d{2})\s+(?:and|to)\s+(19\d{2}|20\d{2})\b",
        normalized_question,
    )
    if between_match:
        return safe_int(between_match.group(1)), safe_int(between_match.group(2)), 0.95

    after_match = re.search(
        r"\b(?:after|newer than|since)\s+(19\d{2}|20\d{2})\b",
        normalized_question,
    )
    if after_match:
        return safe_int(after_match.group(1)), None, 0.92

    before_match = re.search(
        r"\b(?:before|older than)\s+(19\d{2}|20\d{2})\b",
        normalized_question,
    )
    if before_match:
        return None, safe_int(before_match.group(1)), 0.92

    exact_match = re.search(
        r"\b(?:vintage)\s+(19\d{2}|20\d{2})\b",
        normalized_question,
    )
    if exact_match:
        year = safe_int(exact_match.group(1))
        return year, year, 0.92

    return None, None, None


def extract_abv_filters(question: str) -> tuple[float | None, float | None, float | None]:
    """
    Extract alcohol percentage constraints.
    """
    normalized_question = normalize_text(question)

    between_match = re.search(
        r"\b(?:between|from)\s+(\d+(?:\.\d+)?)\s*%\s+(?:and|to)\s+(\d+(?:\.\d+)?)\s*%\b",
        normalized_question,
    )
    if between_match:
        return safe_float(between_match.group(1)), safe_float(between_match.group(2)), 0.9

    min_match = re.search(
        r"\b(?:abv|alcohol)\s+(?:above|over|at least|minimum of)\s*(\d+(?:\.\d+)?)\s*%\b",
        normalized_question,
    )
    if min_match:
        return safe_float(min_match.group(1)), None, 0.88

    max_match = re.search(
        r"\b(?:abv|alcohol)\s+(?:below|under|less than)\s*(\d+(?:\.\d+)?)\s*%\b",
        normalized_question,
    )
    if max_match:
        return None, safe_float(max_match.group(1)), 0.88

    return None, None, None


def extract_volume_ml(question: str) -> tuple[int | None, float | None]:
    """
    Extract bottle size constraints like 750ml or 1.5L.
    """
    normalized_question = normalize_text(question)

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(ml|l|liter|liters|litre|litres)\b",
        normalized_question,
    )
    if not match:
        return None, None

    amount = safe_float(match.group(1))
    unit = match.group(2)

    if amount is None:
        return None, None

    return liters_to_ml(amount, unit), 0.92


def detect_color(question: str) -> tuple[WineColor | None, float | None]:
    """
    Detect color/style terms directly from the question.
    """
    normalized_question = f" {normalize_text(question)} "

    if " sparkling " in normalized_question:
        return WineColor.SPARKLING, 0.98

    if " fortified " in normalized_question:
        return WineColor.FORTIFIED, 0.98

    if " dessert " in normalized_question:
        return WineColor.DESSERT, 0.98

    if " white " in normalized_question:
        return WineColor.WHITE, 0.98

    if " red " in normalized_question:
        return WineColor.RED, 0.98

    if " rose " in normalized_question or " rosé " in normalized_question or " rosee " in normalized_question:
        return WineColor.ROSE, 0.98

    if " other " in normalized_question:
        return WineColor.OTHER, 0.95

    return None, None


def detect_occasion(question: str) -> tuple[Occasion | None, float | None]:
    """
    Detect recommendation occasions.
    """
    normalized_question = normalize_text(question)

    if "housewarming" in normalized_question:
        return Occasion.HOUSEWARMING, 0.98

    if "celebration" in normalized_question or "celebrate" in normalized_question:
        return Occasion.CELEBRATION, 0.9

    if "dinner" in normalized_question:
        return Occasion.DINNER, 0.88

    if "gift" in normalized_question:
        return Occasion.GIFT, 0.95

    return None, None


def detect_sort_preference(question: str) -> tuple[SortBy, float | None]:
    """
    Detect sort language such as cheapest, best rated, or most expensive.
    """
    normalized_question = normalize_text(question)

    if has_any_phrase(normalized_question, ["cheapest", "least expensive", "lowest price"]):
        return SortBy.PRICE_ASC, 0.98

    if has_any_phrase(normalized_question, ["most expensive", "highest price", "priciest"]):
        return SortBy.PRICE_DESC, 0.98

    if has_any_phrase(normalized_question, ["best rated", "highest rated", "top rated", "best wine", "best wines"]):
        return SortBy.BEST_SCORE_DESC, 0.95

    if has_any_phrase(normalized_question, ["value", "best value"]):
        return SortBy.VALUE_DESC, 0.9

    if has_any_phrase(normalized_question, ["newest vintage"]):
        return SortBy.VINTAGE_DESC, 0.88

    return SortBy.RELEVANCE, None


def is_recommendation_query(question: str) -> bool:
    """
    Detect recommendation-style prompts.
    """
    normalized_question = normalize_text(question)
    return bool(
        re.search(
            r"\b(recommend|suggest|something nice|pick a wine|good bottle|gift)\b",
            normalized_question,
        )
    )


def mentions_varietal_focus(question: str) -> bool:
    """
    Detect prompts that explicitly ask for grape/varietal-based guidance.
    """
    normalized_question = normalize_text(question)
    return bool(
        re.search(
            r"\b(varietal|grape|grapes)\b",
            normalized_question,
        )
    )


def should_ask_for_clarification(
    question: str,
    filters: QueryFilters,
    occasion: Occasion | None,
    detected_sort: SortBy,
) -> tuple[bool, list[str], str | None]:
    """
    Decide whether the parser should ask the user for one more detail.
    """
    normalized_question = normalize_text(question)
    active_filters = filters.active()

    is_reco = is_recommendation_query(question) or occasion is not None

    # Recommendation / gift flows should require a budget first.
    if is_reco:
        if filters.min_price is None and filters.max_price is None:
            return (
                True,
                ["budget"],
                "Please add a budget, for example under $25, under $50, or between $30 and $60.",
            )

    # If the user explicitly wants grape / varietal-based guidance,
    # ask for the varietal before asking for color.
    if is_reco and mentions_varietal_focus(question) and not filters.varietal:
        return (
            True,
            ["varietal"],
            "Please name a varietal or grape, for example Chardonnay, Pinot Noir, or Cabernet Sauvignon.",
        )

    # After budget, recommendation / gift flows should usually require a color
    # unless the user already gave a color or a varietal.
    if is_reco:
        if filters.color is None and not filters.varietal:
            return (
                True,
                ["color"],
                "Please choose a style like red, white, sparkling, or rosé.",
            )

    # Generic recommendation with no useful detail at all.
    if re.search(r"\b(recommend|suggest|something nice|pick a wine|good bottle)\b", normalized_question):
        if not active_filters:
            return (
                True,
                ["budget_or_style"],
                "Please add one detail like budget, color, region, producer, appellation, or varietal.",
            )

    has_browse_signal = has_any_phrase(normalized_question, BROWSE_KEYWORDS)
    if not active_filters and occasion is None and detected_sort == SortBy.RELEVANCE and not has_browse_signal:
        return (
            True,
            ["budget_or_style"],
            "Please add one detail like budget, color, region, producer, appellation, or varietal.",
        )

    return False, [], None
