"""
pipeline.py

This file connects the full backend flow:
question ->  4 parser -> retrieval ->  responder

"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

import pandas as pd

from backend.core.schemas import StructuredWineQuery
from backend.services.responder import build_response
from backend.services.retrieval import retrieve_wines


ParserFunction = Callable[[str], StructuredWineQuery | dict[str, Any]]


def _resolve_parser_function() -> ParserFunction:
    """
    Try to find the Step 4 parser without forcing one exact file/function name.

    This makes Step 7 easier to integrate with your existing parser code.
    If your parser has a different location or name, update this function once.
    """
    candidate_modules = [
        "backend.services.parser",
        "backend.services.query_parser",
        "backend.services.intent_parser",
    ]

    candidate_functions = [
        "parse_question",
        "parse_user_query",
        "parse_query",
        "build_structured_query",
    ]

    for module_name in candidate_modules:
        try:
            module = import_module(module_name)
        except ModuleNotFoundError:
            continue

        for function_name in candidate_functions:
            function = getattr(module, function_name, None)
            if callable(function):
                return function

    raise RuntimeError(
        "Could not find your Step 4 parser function. "
        "Update _resolve_parser_function() in backend/services/pipeline.py "
        "to point to your real parser."
    )


def _normalize_structured_query(
    parsed_output: StructuredWineQuery | dict[str, Any],
) -> StructuredWineQuery:
    """
    Normalize parser output into a StructuredWineQuery.

    This accepts either:
    - an already-built StructuredWineQuery
    - a plain dict that matches the schema
    """
    if isinstance(parsed_output, StructuredWineQuery):
        return parsed_output

    return StructuredWineQuery.model_validate(parsed_output)


def run_query_pipeline(
    question: str,
    df: pd.DataFrame,
    limit_override: int | None = None,
) -> dict[str, Any]:
    """
    Run the complete app pipeline for one user question.

    Flow:
    1. Parse natural-language question into StructuredWineQuery
    2. Retrieve matching wines
    3. Build grounded response text
    4. Return final payload for the API
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    parser_function = _resolve_parser_function()
    parsed_output = parser_function(question.strip())
    structured_query = _normalize_structured_query(parsed_output)

    # Allow API callers to override the result limit without changing parser code.
    if limit_override is not None:
        structured_query = structured_query.model_copy(update={"limit": limit_override})

    retrieval_result = retrieve_wines(df, structured_query)
    final_response = build_response(structured_query, retrieval_result)

    return final_response