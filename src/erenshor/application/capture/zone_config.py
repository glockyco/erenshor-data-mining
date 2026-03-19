from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

CONFIG_PATH = Path("src/maps/src/lib/data/zone-capture-config.json")


def load_zone_config(repo_root: Path) -> dict[str, Any]:
    """Load zone capture configuration from the repo."""
    path = repo_root / CONFIG_PATH
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def save_zone_config(repo_root: Path, config: dict[str, Any]) -> None:
    """Write zone capture configuration back to disk."""
    path = repo_root / CONFIG_PATH
    path.write_text(json.dumps(config, indent=2) + "\n")
    logger.info(f"Wrote zone config: {path}")


def get_zone_keys(config: dict[str, Any], zones: list[str] | None = None) -> list[str]:
    """Return sorted zone keys, validating any explicit selection."""
    if zones:
        unknown = set(zones) - set(config.keys())
        if unknown:
            raise ValueError(f"Unknown zones: {', '.join(sorted(unknown))}")
        return zones
    return sorted(config.keys())
