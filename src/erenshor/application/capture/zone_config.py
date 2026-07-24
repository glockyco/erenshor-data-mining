from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

CONFIG_RELATIVE_PATH = Path("src/lib/data/zone-capture-config.json")


def load_zone_config(config_path: Path) -> dict[str, Any]:
    """Load zone capture configuration from an explicit maps path."""
    result: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    return result


def save_zone_config(config_path: Path, config: dict[str, Any]) -> None:
    """Write zone capture configuration to an explicit maps path."""
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    logger.info(f"Wrote zone config: {config_path}")


def get_zone_keys(config: dict[str, Any], zones: list[str] | None = None) -> list[str]:
    """Return sorted zone keys, validating any explicit selection."""
    if zones:
        unknown = set(zones) - set(config.keys())
        if unknown:
            raise ValueError(f"Unknown zones: {', '.join(sorted(unknown))}")
        return zones
    return sorted(config.keys())
