from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz


def normalize_text(text: str) -> str:
    """
    Lowercase, remove accents, remove most punctuation, and collapse spaces.

    This makes matching much more stable across user phrasing and dataset values.
    """
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9.%]+", " ", text)
    return " ".join(text.split())


def exact_phrase_match(question: str, candidates: list[str]) -> tuple[str, float] | None:
    """
    Return the first exact phrase match found inside the question.

    Longer candidates should already appear earlier in the list so the parser
    prefers more specific values when an exact match is available.
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

    We score each candidate against the normalized question and keep the best
    one only if it clears the cutoff.
    """
    normalized_question = normalize_text(question)
    if not normalized_question:
        return None

    best_candidate: str | None = None
    best_score = -1.0

    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)

        # Very short fuzzy candidates tend to create noisy false positives,
        # so skip them.
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

    This keeps matching deterministic and grounded while still allowing some
    tolerance for typos or phrasing differences.
    """
    exact_match = exact_phrase_match(question, candidates)
    if exact_match is not None:
        return exact_match

    if allow_fuzzy:
        return fuzzy_phrase_match(question, candidates, score_cutoff=score_cutoff)

    return None


def has_any_phrase(question: str, phrases: list[str]) -> bool:
    """
    Return True if any phrase from the list appears in the normalized question.
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
    """
    Safely convert a string-like value to float.
    """
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def safe_int(value: str | None) -> int | None:
    """
    Safely convert a string-like value to int.
    """
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None