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
        use_enum_values=True,
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
class UnresolvedEntity(BaseModel):
    """
    A user-provided entity that looked meaningful but could not be matched
    to the current dataset.

    Examples:
    - country_or_region: "India"
    - producer: "Some Winery"
    - varietal: "Mystery Grape"

    In Phase 2 we start by tracking these entities. In the next step,
    retrieval/responders will use them to avoid returning misleading results.
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # Broad field bucket for the unresolved value.
    field: str = Field(..., min_length=1)

    # The actual user-facing value we failed to resolve.
    value: str = Field(..., min_length=1)

    # Optional original phrase or context from the question.
    phrase: str | None = None

class StructuredWineQuery(BaseModel):
    """
    Main internal query contract for the app.
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

    # Keep limit for backward compatibility with the current codebase.
    # In Phase 3, page_size becomes the main paging control.
    limit: int = Field(default=10, ge=1, le=50)

    # Pagination fields for V2 browsing.
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=20)

    # Parser confidence is useful for Step 4 and later fallback logic.
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # These fields help us handle vague / unsupported questions honestly.
    needs_clarification: bool = False
    clarification_message: str | None = None
    missing_fields: list[str] = Field(default_factory=list)

    unsupported_reason: str | None = None
    occasion: Occasion | None = None

    # Explicit user-provided values that looked meaningful but did not match
    # the current dataset.
    unresolved_entities: list[UnresolvedEntity] = Field(default_factory=list)

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

class DatasetFieldMetadata(BaseModel):
    """
    Metadata for one text-like dataset field such as country, region, producer,
    varietal, or color.
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    field_name: str
    canonical_column: str | None = None

    # All distinct canonical values found in the dataset for this field.
    values: list[str] = Field(default_factory=list)

    # Normalized text -> canonical dataset value
    normalized_to_canonical: dict[str, str] = Field(default_factory=dict)

    # Canonical value -> frequency count in the dataset
    counts: dict[str, int] = Field(default_factory=dict)

    # Most common values for suggestions / UI chips
    top_values: list[str] = Field(default_factory=list)


class DatasetNumericRangeMetadata(BaseModel):
    """
    Min/max metadata for one numeric dataset field such as price, vintage, or ABV.
    """
    model_config = ConfigDict(extra="forbid")

    field_name: str
    canonical_column: str | None = None
    min_value: float | int | None = None
    max_value: float | int | None = None


class DatasetMetadata(BaseModel):
    """
    Cached metadata built from the current dataset.

    This becomes the shared source of truth for:
    - which canonical fields exist
    - which unique values exist in the dataset
    - which numeric ranges exist
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    dataset_path: str
    dataset_mtime: float

    available_columns: list[str] = Field(default_factory=list)

    # app field name -> actual dataframe column name
    canonical_columns: dict[str, str | None] = Field(default_factory=dict)

    # text/categorical field metadata
    field_indexes: dict[str, DatasetFieldMetadata] = Field(default_factory=dict)

    # numeric field metadata
    numeric_ranges: dict[str, DatasetNumericRangeMetadata] = Field(default_factory=dict)