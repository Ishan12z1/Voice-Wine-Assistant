from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QueryIntent(str, Enum):
    # Main query modes the backend understands.
    BROWSE_COLLECTION = "browse_collection"
    BEST_RATED_UNDER_BUDGET = "best_rated_under_budget"
    CHEAPEST = "cheapest"
    MOST_EXPENSIVE = "most_expensive"
    GIFT_RECOMMENDATION = "gift_recommendation"
    AMBIGUOUS_REQUEST = "ambiguous_request"
    UNSUPPORTED_REQUEST = "unsupported_request"


class SortBy(str, Enum):
    # Ranking strategies used later by retrieval/ranking.
    RELEVANCE = "relevance"
    BEST_SCORE_DESC = "best_score_desc"
    AVG_SCORE_DESC = "avg_score_desc"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    VALUE_DESC = "value_desc"
    NAME_ASC = "name_asc"
    VINTAGE_DESC = "vintage_desc"


class WineColor(str, Enum):
    RED = "red"
    WHITE = "white"
    SPARKLING = "sparkling"
    ROSE = "rose"
    FORTIFIED = "fortified"
    DESSERT = "dessert"
    OTHER = "other"


class Occasion(str, Enum):
    GIFT = "gift"
    HOUSEWARMING = "housewarming"
    DINNER = "dinner"
    CELEBRATION = "celebration"


class QueryFilters(BaseModel):
    """
    All dataset-backed filters live here.

    The parser can set any combination of these fields.
    Retrieval will later apply them with AND logic.
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # Text / categorical filters
    name: str | None = None
    producer: str | None = None
    country: str | None = None
    region: str | None = None
    appellation: str | None = None
    varietal: str | None = None
    color: WineColor | None = None

    # Numeric filters
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)

    min_vintage: int | None = Field(default=None, ge=1000, le=2100)
    max_vintage: int | None = Field(default=None, ge=1000, le=2100)

    min_abv: float | None = Field(default=None, ge=0, le=100)
    max_abv: float | None = Field(default=None, ge=0, le=100)

    volume_ml: int | None = Field(default=None, ge=1)

    min_best_score: float | None = Field(default=None, ge=0, le=100)
    min_avg_score: float | None = Field(default=None, ge=0, le=100)
    min_rating_count: int | None = Field(default=None, ge=0)

    # Optional data-quality-aware flags
    require_varietal: bool | None = None
    require_vintage: bool | None = None

    @field_validator(
        "name",
        "producer",
        "country",
        "region",
        "appellation",
        "varietal",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        return " ".join(text.split())

    @model_validator(mode="after")
    def validate_ranges(self) -> "QueryFilters":
        # Keep all min/max ranges sane.
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot be greater than max_price")

        if self.min_vintage is not None and self.max_vintage is not None:
            if self.min_vintage > self.max_vintage:
                raise ValueError("min_vintage cannot be greater than max_vintage")

        if self.min_abv is not None and self.max_abv is not None:
            if self.min_abv > self.max_abv:
                raise ValueError("min_abv cannot be greater than max_abv")

        return self

    def active(self) -> dict[str, Any]:
        # Only return filters that are actually set.
        return {
            key: value
            for key, value in self.model_dump().items()
            if value is not None
        }


class StructuredWineQuery(BaseModel):
    """
    Main internal query contract for the app.

    Step 4 will parse raw user text into this object.
    Step 5+ will consume it deterministically.
    """
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    original_question: str = Field(..., min_length=1)

    intent: QueryIntent = QueryIntent.BROWSE_COLLECTION
    filters: QueryFilters = Field(default_factory=QueryFilters)

    sort_by: SortBy = SortBy.RELEVANCE
    limit: int = Field(default=10, ge=1, le=50)

    # Parser confidence is useful for Step 4 and later fallback logic.
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # These fields help us handle vague / unsupported questions honestly.
    needs_clarification: bool = False
    clarification_message: str | None = None
    missing_fields: list[str] = Field(default_factory=list)

    unsupported_reason: str | None = None
    occasion: Occasion | None = None

    @model_validator(mode="after")
    def fill_defaults_from_intent(self) -> "StructuredWineQuery":
        # Default ranking policy depends on intent.
        if self.intent == QueryIntent.BEST_RATED_UNDER_BUDGET:
            self.sort_by = SortBy.BEST_SCORE_DESC

        elif self.intent == QueryIntent.CHEAPEST:
            self.sort_by = SortBy.PRICE_ASC

        elif self.intent == QueryIntent.MOST_EXPENSIVE:
            self.sort_by = SortBy.PRICE_DESC

        elif self.intent == QueryIntent.GIFT_RECOMMENDATION:
            self.sort_by = SortBy.VALUE_DESC

        if self.intent == QueryIntent.AMBIGUOUS_REQUEST:
            self.needs_clarification = True

        if self.intent != QueryIntent.UNSUPPORTED_REQUEST:
            self.unsupported_reason = None

        return self

    def active_filters(self) -> dict[str, Any]:
        return self.filters.active()


# A few examples make the schema easier to understand and demo.
EXAMPLE_STRUCTURED_QUERIES = [
    {
        "original_question": "Best-rated red wines under $50",
        "intent": "best_rated_under_budget",
        "filters": {
            "color": "red",
            "max_price": 50,
        },
        "sort_by": "best_score_desc",
        "limit": 5,
        "confidence": 0.98,
    },
    {
        "original_question": "Show me Cabernet Sauvignon from California",
        "intent": "browse_collection",
        "filters": {
            "varietal": "Cabernet Sauvignon",
            "region": "California",
        },
        "sort_by": "relevance",
        "limit": 10,
        "confidence": 0.96,
    },
    {
        "original_question": "Show me wines from Stag's Leap Wine Cellars under $100",
        "intent": "browse_collection",
        "filters": {
            "producer": "Stag's Leap Wine Cellars",
            "max_price": 100,
        },
        "sort_by": "relevance",
        "limit": 10,
        "confidence": 0.95,
    },
    {
        "original_question": "Recommend a housewarming gift",
        "intent": "gift_recommendation",
        "filters": {},
        "sort_by": "value_desc",
        "limit": 5,
        "confidence": 0.83,
        "occasion": "housewarming",
    },
]