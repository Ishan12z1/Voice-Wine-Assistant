from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz


# Default source used by the parser for entity vocab.
DEFAULT_VOCAB_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "processed"
    / "wines_enriched.csv"
)


def normalize_text(text: str) -> str:
    """
    Lowercase, remove accents, remove most punctuation, and collapse spaces.
    This makes matching much more stable.
    """
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9.%]+", " ", text)
    return " ".join(text.split())


@lru_cache(maxsize=4)
def load_parser_vocabulary(data_path: str | None = None) -> dict[str, list[str]]:
    """
    Load canonical values from the cleaned dataset once and cache them.

    The parser uses these values for exact and fuzzy matching.
    """
    path = Path(data_path) if data_path else DEFAULT_VOCAB_PATH

    # Return empty vocab gracefully if the processed file is missing.
    base_vocab = {
        "name": [],
        "producer": [],
        "country": [],
        "region": [],
        "appellation": [],
        "varietal": [],
        "color": ["sparkling", "fortified", "dessert", "white", "red", "rose", "rosé", "other"],
    }

    if not path.exists():
        return base_vocab

    df = pd.read_csv(path)

    for field in ["name", "producer", "country", "region", "appellation", "varietal"]:
        values = (
            df[field]
            .dropna()
            .astype(str)
            .str.strip()
        )
        unique_values = sorted(
            {value for value in values if value},
            key=lambda value: (-len(value), value.lower()),
        )
        base_vocab[field] = unique_values

    return base_vocab


def exact_phrase_match(question: str, candidates: list[str]) -> tuple[str, float] | None:
    """
    Return the first exact phrase match found inside the question.
    Longer candidates should already appear earlier in the list.
    """
    normalized_question = f" {normalize_text(question)} "

    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if normalized_candidate and f" {normalized_candidate} " in normalized_question:
            return candidate, 100.0

    return None


def fuzzy_phrase_match(
    question: str,
    candidates: list[str],
    *,
    score_cutoff: float = 90,
) -> tuple[str, float] | None:
    """
    Fuzzy match a dataset value against the full question.
    We use partial_ratio and token_set_ratio and keep the better score.
    """
    normalized_question = normalize_text(question)
    if not normalized_question:
        return None

    best_candidate: str | None = None
    best_score = -1.0

    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)

        # Skip ultra-short fuzzy matches because they create noise.
        if len(normalized_candidate) < 4:
            continue

        score = max(
            fuzz.partial_ratio(normalized_question, normalized_candidate),
            fuzz.token_set_ratio(normalized_question, normalized_candidate),
        )

        if score > best_score:
            best_score = float(score)
            best_candidate = candidate

    if best_candidate is not None and best_score >= score_cutoff:
        return best_candidate, best_score

    return None


def best_value_match(
    question: str,
    candidates: list[str],
    *,
    score_cutoff: float = 90,
    allow_fuzzy: bool = True,
) -> tuple[str, float] | None:
    """
    Prefer exact phrase matches first, then fall back to fuzzy matching.
    """
    exact_match = exact_phrase_match(question, candidates)
    if exact_match is not None:
        return exact_match

    if allow_fuzzy:
        return fuzzy_phrase_match(question, candidates, score_cutoff=score_cutoff)

    return None


def has_any_phrase(question: str, phrases: list[str]) -> bool:
    """
    Small helper for keyword groups.
    """
    normalized_question = normalize_text(question)
    return any(phrase in normalized_question for phrase in phrases)


def liters_to_ml(value: float, unit: str) -> int:
    """
    Convert bottle size values into ml.
    """
    normalized_unit = normalize_text(unit)

    if normalized_unit in {"l", "liter", "liters", "litre", "litres"}:
        return int(round(value * 1000))

    return int(round(value))


def safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None