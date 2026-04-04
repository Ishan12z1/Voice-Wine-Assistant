from __future__ import annotations
import re 

from backend.core.schemas import (
    Occasion,
    QueryFilters,
    QueryIntent,
    SortBy,
    StructuredWineQuery,
    WineColor,
)
from backend.utils.helpers import (
    best_value_match,
    has_any_phrase,
    liters_to_ml,
    load_parser_vocabulary,
    normalize_text,
    safe_float,safe_int,
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

# These are the filter fields Step 4 is allowed to populate.
# Generic browse words help decide whether a broad question is still usable.
BROWSE_KEYWORDS = [
    "show me",
    "find",
    "browse",
    "list",
    "what do you have",
    "what wines do you have",
    "give me",
]


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
    return StructuredWineQuery(
        original_question=question,
        intent=QueryIntent.UNSUPPORTED_REQUEST,
        filters=QueryFilters(),
        sort_by=SortBy.RELEVANCE,
        limit=10,
        confidence=confidence,
        unsupported_reason=reason,
    )


def detect_unsupported_reason(question: str) -> str | None:
    normalized_question = normalize_text(question)

    for pattern, reason in UNSUPPORTED_PATTERNS:
        if re.search(pattern, normalized_question):
            return reason

    return None


def extract_limit(question: str) -> int | None:
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
    Returns: (min_price, max_price, confidence_contribution)

    Strong price matches:
    - under $50
    - under 50 dollars
    - budget under 50

    Lenient fallback:
    - under 100
    - above 80

    But lenient fallback should only run when no other numeric field
    like score, vintage, ABV, or volume has already claimed the number.
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

    # Lenient fallback: allow plain "under 100" only if nothing else numeric is competing.
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
    Returns: (min_best_score, confidence_contribution)
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
        year = safe_int(exact_match.group(1) or exact_match.group(2))
        return year, year, 0.92

    return None, None, None


def extract_abv_filters(question: str) -> tuple[float | None, float | None, float | None]:
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
    Detect wine color from common words in the question.
    Keep this simple and deterministic.
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


def apply_dataset_matches(question: str, filters: QueryFilters) -> tuple[QueryFilters, list[float]]:
    """
    Fill country / region / appellation / producer / varietal / name from real dataset vocab.
    """
    vocab = load_parser_vocabulary()
    scores: list[float] = []
    normalized_question = normalize_text(question)

    country_match = best_value_match(question, vocab["country"], score_cutoff=93, allow_fuzzy=True)
    if country_match:
        filters.country = country_match[0]
        scores.append(country_match[1] / 100)

    region_match = best_value_match(question, vocab["region"], score_cutoff=91, allow_fuzzy=True)
    if region_match:
        filters.region = region_match[0]
        scores.append(region_match[1] / 100)

    appellation_match = best_value_match(question, vocab["appellation"], score_cutoff=91, allow_fuzzy=True)
    if appellation_match:
        filters.appellation = appellation_match[0]
        scores.append(appellation_match[1] / 100)

    producer_match = best_value_match(question, vocab["producer"], score_cutoff=93, allow_fuzzy=True)
    if producer_match:
        filters.producer = producer_match[0]
        scores.append(producer_match[1] / 100)

    varietal_match = best_value_match(question, vocab["varietal"], score_cutoff=92, allow_fuzzy=True)
    if varietal_match:
        filters.varietal = varietal_match[0]
        scores.append(varietal_match[1] / 100)

    # Wine name matching is noisy, so keep it exact-only unless the question explicitly says "named" or "called".
    if re.search(r"\b(named|called)\b", normalized_question):
        name_match = best_value_match(question, vocab["name"], score_cutoff=96, allow_fuzzy=False)
        if name_match:
            filters.name = name_match[0]
            scores.append(name_match[1] / 100)

    # If the same value matched both region and appellation, keep one to avoid overly restrictive AND filtering.
    if filters.region and filters.appellation:
        if normalize_text(filters.region) == normalize_text(filters.appellation):
            if "appellation" in normalized_question or "ava" in normalized_question:
                filters.region = None
            else:
                filters.appellation = None

    return filters, scores


def infer_intent(
    question: str,
    filters: QueryFilters,
    occasion: Occasion | None,
    detected_sort: SortBy,
) -> QueryIntent:


    if occasion is not None:
        return QueryIntent.GIFT_RECOMMENDATION

    if detected_sort == SortBy.PRICE_ASC:
        return QueryIntent.CHEAPEST

    if detected_sort == SortBy.PRICE_DESC:
        return QueryIntent.MOST_EXPENSIVE

    if detected_sort == SortBy.BEST_SCORE_DESC and filters.max_price is not None:
        return QueryIntent.BEST_RATED_UNDER_BUDGET

    return QueryIntent.BROWSE_COLLECTION

def is_recommendation_query(question: str) -> bool:
    normalized_question = normalize_text(question)
    return bool(
        re.search(
            r"\b(recommend|suggest|something nice|pick a wine|good bottle|gift)\b",
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

def mentions_varietal_focus(question: str) -> bool:
    normalized_question = normalize_text(question)
    return bool(
        re.search(
            r"\b(varietal|grape|grapes)\b",
            normalized_question,
        )
    )

def parse_query(text: str) -> StructuredWineQuery:
    """
    Step 4 parser.

    This function translates a raw user question into a structured query object
    using deterministic rules and dataset-backed matching.
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
        )

    unsupported_reason = detect_unsupported_reason(cleaned)
    if unsupported_reason:
        return make_unsupported_query(
            question=cleaned,
            reason=unsupported_reason,
            confidence=0.99,
        )

    filters = QueryFilters()
    confidence_parts: list[float] = []

        # Numeric filters
    # Parse specific numeric fields first so they win before price fallback.

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

    # Dataset-backed entity matching
    filters, match_scores = apply_dataset_matches(cleaned, filters)
    confidence_parts.extend(match_scores)

    # If the user explicitly asks for varietal / grape-focused results,
    # require rows to actually have varietal data.
    if mentions_varietal_focus(cleaned):
        filters.require_varietal = True

    # If the user already matched a specific varietal, also require varietal data.
    if filters.varietal:
        filters.require_varietal = True

    # Only allow loose price parsing when no other numeric field already matched.
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

    # Handle vague recommendation requests honestly.
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
    )
    # Detect sort intent like cheapest / most expensive / best rated.

    intent = infer_intent(cleaned, filters, occasion, detected_sort)

    # For broad but usable browse queries like "show me wines", keep them valid.
    if not filters.active() and occasion is None and detected_sort == SortBy.RELEVANCE:
        if has_any_phrase(cleaned, BROWSE_KEYWORDS):
            return make_query(
                question=cleaned,
                intent=QueryIntent.BROWSE_COLLECTION,
                filters=filters,
                sort_by=SortBy.RELEVANCE,
                limit=limit,
                confidence=0.6,
            )

    # Build a simple confidence score from signals we actually detected.
    if confidence_parts:
        confidence = round(sum(confidence_parts) / len(confidence_parts), 2)
    else:
        confidence = 0.55

    # Keep "best-rated ..." browse queries sorted by score even without a budget.
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
    )


if __name__ == "__main__":
    examples = [
        "Best-rated red wines under $50",
        "Show me Cabernet Sauvignon from California",
        "Find wines from Stag's Leap Wine Cellars under 100",
        "Show Napa Valley wines with score above 92",
        "Cheapest white wine",
        "Most expensive bottle from Burgundy",
        "Recommend a housewarming gift",
        "Show me 750ml sparkling wines from Champagne",
        "Teach me how tannins work",
        "Recommend something nice",
        "Show me wines",
    ]

    for question in examples:
        result = parse_query(question)
        print("-" * 80)
        print(question)
        print(result.model_dump())