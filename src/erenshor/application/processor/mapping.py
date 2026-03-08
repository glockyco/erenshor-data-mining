"""Mapping override loader for the Layer 2 processor.

Reads mapping.json and returns a lookup dict consumed by every entity
processor.  The only responsibility of this module is loading and
validating the file — applying overrides to individual records is done
in each entity processor.

mapping.json schema (version 2.0):

    {
        "metadata": { ... },
        "rules": {
            "<stable_key>": {
                "wiki_page_name": "<string or null>",
                "display_name": "<string>",
                "image_name":   "<string>"
            },
            ...
        }
    }

A null wiki_page_name means the entity is excluded from the clean DB
entirely.  display_name and image_name are always present for
non-excluded entities; excluded entities may omit them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from loguru import logger


class MappingOverride(TypedDict):
    display_name: str
    wiki_page_name: str | None  # None → excluded
    image_name: str


def load_mapping(path: Path) -> dict[str, MappingOverride]:
    """Load mapping.json and return a stable-key → override dict.

    Stable keys in mapping.json are already lowercase and colon-separated
    (matching the StableKey values in the raw DB), so no normalisation is
    applied.

    Extra fields in each rule (e.g., ``mapping_type``, ``reason``) are
    silently ignored.

    Args:
        path: Path to mapping.json.

    Returns:
        Dict mapping stable_key to MappingOverride.

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

    result: dict[str, MappingOverride] = {}
    errors: list[str] = []

    for stable_key, rule in rules.items():
        if not isinstance(rule, dict):
            errors.append(f"{stable_key}: rule must be an object")
            continue

        wiki_page_name: str | None = rule.get("wiki_page_name")
        display_name: str | None = rule.get("display_name")
        image_name: str | None = rule.get("image_name")
        excluded = "wiki_page_name" in rule and wiki_page_name is None

        if not excluded:
            if display_name is None:
                errors.append(f"{stable_key}: non-excluded rule missing 'display_name'")
                continue
            if image_name is None:
                errors.append(f"{stable_key}: non-excluded rule missing 'image_name'")
                continue
            if wiki_page_name is None:
                # wiki_page_name key absent entirely; treat as excluded? No —
                # the operations.py logic requires the key to be present and
                # null to mean excluded.  Absent key means no override.
                # But if display_name is provided we expect wiki_page_name too.
                errors.append(f"{stable_key}: non-excluded rule missing 'wiki_page_name'")
                continue

        result[stable_key] = MappingOverride(
            display_name=display_name if display_name is not None else "",
            wiki_page_name=wiki_page_name,
            image_name=image_name if image_name is not None else "",
        )

    if errors:
        summary = "\n  ".join(errors[:10])
        suffix = f"\n  ... and {len(errors) - 10} more" if len(errors) > 10 else ""
        raise ValueError(f"mapping.json has {len(errors)} invalid rule(s):\n  {summary}{suffix}")

    logger.info(f"Loaded {len(result)} mapping rules from {path}")
    return result
