from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


def load_project_env() -> None:
    """
    Load simple KEY=VALUE pairs from the repo-root .env file into os.environ.

    Existing environment variables win over .env values so shell overrides still work.
    """
    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def resolve_project_path(path_value: str) -> str:
    """
    Resolve a possibly relative path against the repo root.
    """
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    return str((PROJECT_ROOT / candidate).resolve())


def get_configured_dataset_path() -> str:
    """
    Return the active dataset path from environment configuration.
    """
    load_project_env()

    dataset_path = os.getenv("WINE_DATASET_PATH")
    if not dataset_path:
        raise RuntimeError(
            "WINE_DATASET_PATH is not set. Add it to the repo .env file or export it in your shell."
        )

    return resolve_project_path(dataset_path)
