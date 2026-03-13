"""Mapping override loader for the Layer 2 processor.

Reads mapping.json and returns lookup dicts consumed by every entity
processor.  The only responsibility of this module is loading and
validating the file — applying overrides to individual records is done
in each entity processor.

mapping.json schema (version 2.0):

    {
        "metadata": { ... },
        "rules": {
            "<character_stable_key>": {
                "wiki_page_name":    "<string or null>",
                "display_name":      "<string>",
                "image_name":        "<string>",
                "is_wiki_generated": 0 or 1,
                "is_map_visible":    0 or 1
            },
            "<spawn_point_stable_key>": {
                "is_wiki_generated": 0 or 1,
                "is_map_visible":    0 or 1
            },
            ...
        }
    }

Character keys start with "character:" and require display_name and
image_name. Spawn keys start with "spawn:" and only carry visibility
flags. is_wiki_generated and is_map_visible default to 1 when absent
in either rule type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from loguru import logger


class MappingOverride(TypedDict):
    display_name: str
    wiki_page_name: str | None
    image_name: str
    is_wiki_generated: int
    is_map_visible: int


class SpawnMappingOverride(TypedDict):
    is_wiki_generated: int
    is_map_visible: int


def load_mapping(
    path: Path,
) -> tuple[dict[str, MappingOverride], dict[str, SpawnMappingOverride]]:
    """Load mapping.json and return (character_overrides, spawn_overrides).

    Rules are split by key prefix: keys starting with "character:" are
    character overrides; keys starting with "spawn:" are spawn-point
    overrides. Character rules require display_name and image_name; spawn
    rules only carry is_wiki_generated and is_map_visible.

    Stable keys in mapping.json are already lowercase and colon-separated
    (matching the StableKey values in the raw DB), so no normalisation is
    applied.

    Extra fields in each rule (e.g., ``mapping_type``, ``reason``) are
    silently ignored.

    Args:
        path: Path to mapping.json.

    Returns:
        Tuple of (character_overrides, spawn_overrides) dicts.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is malformed or a rule is missing required
            fields.
    """
    if not path.exists():
        raise FileNotFoundError(f"mapping.json not found: {path}")

    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"mapping.json is not valid JSON: {exc}") from exc

    rules: dict[str, object] = data.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError("mapping.json 'rules' must be an object")

    character_result: dict[str, MappingOverride] = {}
    spawn_result: dict[str, SpawnMappingOverride] = {}
    errors: list[str] = []

    for stable_key, rule in rules.items():
        if not isinstance(rule, dict):
            errors.append(f"{stable_key}: rule must be an object")
            continue

        if stable_key.startswith("spawn:"):
            spawn_result[stable_key] = SpawnMappingOverride(
                is_wiki_generated=int(rule.get("is_wiki_generated", 1)),
                is_map_visible=int(rule.get("is_map_visible", 1)),
            )
        else:
            wiki_page_name: str | None = rule.get("wiki_page_name")
            display_name: str | None = rule.get("display_name")
            image_name: str | None = rule.get("image_name")

            if display_name is None:
                errors.append(f"{stable_key}: rule missing 'display_name'")
                continue
            if image_name is None:
                errors.append(f"{stable_key}: rule missing 'image_name'")
                continue

            character_result[stable_key] = MappingOverride(
                display_name=display_name,
                wiki_page_name=wiki_page_name,
                image_name=image_name,
                is_wiki_generated=int(rule.get("is_wiki_generated", 1)),
                is_map_visible=int(rule.get("is_map_visible", 1)),
            )

    if errors:
        summary = "\n  ".join(errors[:10])
        suffix = f"\n  ... and {len(errors) - 10} more" if len(errors) > 10 else ""
        raise ValueError(f"mapping.json has {len(errors)} invalid rule(s):\n  {summary}{suffix}")

    logger.info(f"Loaded {len(character_result)} character rules and {len(spawn_result)} spawn rules from {path}")
    return character_result, spawn_result
