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
                "expected_npc_name": "<string, required when display_name overrides NPCName>",
                "is_wiki_generated": 0 or 1,
                "is_map_visible":    0 or 1
            },
            "<spawn_point_stable_key>": {
                "is_wiki_generated": 0 or 1,
                "is_map_visible":    0 or 1
            },
            "<zone_line_stable_key>": {
                "is_usable": 0,
                "reason":    "<why players cannot use the line>"
            },
            ...
        }
    }

Character keys start with "character:" and require display_name and
image_name. Stance keys start with "stance:" and must not carry
image_name: a stance has no icon in the game, and the stance processor
takes the image of the skill that switches to it. Other entity keys require
display_name and image_name. Spawn keys start with "spawn:" or "trigger:"
and only carry visibility flags. is_wiki_generated and is_map_visible
default to 1 when absent in any rule type. Zone line keys start with
"zoneline:" and only exclude a line that players cannot use, with
is_usable 0 and a reason. No rule can make a line usable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NotRequired, TypedDict

from loguru import logger


class MappingOverride(TypedDict):
    display_name: str
    wiki_page_name: str | None
    image_name: str | None
    expected_npc_name: str | None
    is_wiki_generated: int
    is_map_visible: int
    encounter_tier: str | None
    loot_unreachable: bool
    zone_type: NotRequired[str]


ENCOUNTER_TIERS = frozenset({"npc", "chest", "boss", "elite", "enemy"})
ZONE_TYPE_OVERRIDES = frozenset({"Outdoor", "Dungeon", "Event"})


class SpawnMappingOverride(TypedDict):
    is_wiki_generated: int
    is_map_visible: int


def validate_character_name_overrides(
    mapping: dict[str, MappingOverride],
    raw_npc_names: dict[str, str],
) -> None:
    """Reject unpinned display-name overrides and upstream name drift.

    ``expected_npc_name`` is an optimistic-concurrency token for intentional
    renames. A changed game ``NPCName`` must therefore be reviewed instead of
    remaining hidden behind an old display-name override.
    """
    errors: list[str] = []

    for stable_key, override in mapping.items():
        raw_npc_name = raw_npc_names.get(stable_key)
        if raw_npc_name is None:
            continue

        current_name = raw_npc_name.strip()
        display_name = override["display_name"].strip()
        expected_name = override["expected_npc_name"]

        if expected_name is None:
            if display_name != current_name:
                errors.append(
                    f"{stable_key}: display_name {display_name!r} overrides NPCName "
                    f"{current_name!r} without 'expected_npc_name'"
                )
            continue

        if expected_name.strip() != current_name:
            errors.append(
                f"{stable_key}: expected NPCName {expected_name.strip()!r}, "
                f"found {current_name!r}; review or remove the stale override"
            )

    if errors:
        summary = "\n  ".join(errors[:10])
        suffix = f"\n  ... and {len(errors) - 10} more" if len(errors) > 10 else ""
        raise ValueError(
            f"mapping.json has {len(errors)} stale or unpinned character name override(s):\n  {summary}{suffix}"
        )


def load_mapping(
    path: Path,
) -> tuple[dict[str, MappingOverride], dict[str, SpawnMappingOverride], dict[str, str]]:
    """Load mapping.json and return (entity_overrides, spawn_overrides, zone_line_exclusions).

    Keys starting with "spawn:" or "trigger:" are spawn-location overrides.
    Keys starting with "zoneline:" are reviewed exclusions of zone lines that
    players cannot use, which map each line to its reason.
    Other keys are entity overrides. Stance rules must not set image_name, and
    the image_name of their override is None. Other entity rules require
    display_name and image_name. Spawn rules only carry is_wiki_generated
    and is_map_visible.

    Stable keys in mapping.json are already lowercase and colon-separated
    (matching the StableKey values in the raw DB), so no normalisation is
    applied.

    ``expected_npc_name`` pins the raw game name behind an intentional
    display-name override. ``encounter_tier`` replaces the derived tier for a
    character that game data classifies wrongly, and requires a ``reason``.
    ``loot_unreachable`` drops the loot rows of a character that the game
    never kills, and also requires a ``reason``.
    ``zone_type`` retains a reviewed public area classification when the native
    task flag is insufficient and requires a ``reason``. Raid classification
    comes from the exported encounter controllers.
    Other metadata fields such as ``mapping_type`` are ignored.

    Args:
        path: Path to mapping.json.

    Returns:
        Tuple of (character_overrides, spawn_overrides, zone_line_exclusions) dicts.

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
    zone_line_result: dict[str, str] = {}
    errors: list[str] = []

    for stable_key, rule in rules.items():
        if not isinstance(rule, dict):
            errors.append(f"{stable_key}: rule must be an object")
            continue

        if stable_key.startswith("zoneline:"):
            error = _zone_line_error(rule)
            if error is None:
                zone_line_result[stable_key] = rule["reason"].strip()
            else:
                errors.append(f"{stable_key}: {error}")
            continue
        if "is_usable" in rule:
            errors.append(f"{stable_key}: 'is_usable' belongs to a zoneline: rule")
            continue

        if stable_key.startswith(("spawn:", "trigger:")):
            spawn_result[stable_key] = SpawnMappingOverride(
                is_wiki_generated=int(rule.get("is_wiki_generated", 1)),
                is_map_visible=int(rule.get("is_map_visible", 1)),
            )
        else:
            wiki_page_name: str | None = rule.get("wiki_page_name")
            display_name: str | None = rule.get("display_name")
            image_name: str | None = rule.get("image_name")
            expected_npc_name: str | None = rule.get("expected_npc_name")

            if expected_npc_name is not None and not isinstance(expected_npc_name, str):
                errors.append(f"{stable_key}: 'expected_npc_name' must be a string")
                continue
            if display_name is None:
                errors.append(f"{stable_key}: rule missing 'display_name'")
                continue
            if stable_key.startswith("stance:"):
                if image_name is not None:
                    errors.append(
                        f"{stable_key}: a stance rule must not set 'image_name', because the stance "
                        "takes the image of the skill that switches to it"
                    )
                    continue
            elif image_name is None:
                errors.append(f"{stable_key}: rule missing 'image_name'")
                continue
            encounter_tier = rule.get("encounter_tier")
            if encounter_tier is not None:
                if encounter_tier not in ENCOUNTER_TIERS:
                    errors.append(
                        f"{stable_key}: 'encounter_tier' must be one of {sorted(ENCOUNTER_TIERS)}, "
                        f"found {encounter_tier!r}"
                    )
                    continue
                if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
                    errors.append(f"{stable_key}: 'encounter_tier' override requires a 'reason'")
                    continue

            loot_unreachable = rule.get("loot_unreachable", False)
            if not isinstance(loot_unreachable, bool):
                errors.append(f"{stable_key}: 'loot_unreachable' must be true or false")
                continue
            if loot_unreachable and (not isinstance(rule.get("reason"), str) or not rule["reason"].strip()):
                errors.append(f"{stable_key}: 'loot_unreachable' requires a 'reason'")
                continue
            zone_type = rule.get("zone_type")
            if "zone_type" in rule:
                if (
                    not stable_key.startswith("zone:")
                    or not isinstance(zone_type, str)
                    or zone_type not in ZONE_TYPE_OVERRIDES
                ):
                    errors.append(
                        f"{stable_key}: 'zone_type' must be a reviewed {sorted(ZONE_TYPE_OVERRIDES)} for a zone"
                    )
                    continue
                if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
                    errors.append(f"{stable_key}: 'zone_type' requires a 'reason'")
                    continue

            character_result[stable_key] = MappingOverride(
                display_name=display_name,
                wiki_page_name=wiki_page_name,
                image_name=image_name,
                expected_npc_name=expected_npc_name,
                is_wiki_generated=int(rule.get("is_wiki_generated", 1)),
                is_map_visible=int(rule.get("is_map_visible", 1)),
                encounter_tier=encounter_tier,
                loot_unreachable=loot_unreachable,
            )
            if zone_type is not None:
                character_result[stable_key]["zone_type"] = zone_type

    if errors:
        summary = "\n  ".join(errors[:10])
        suffix = f"\n  ... and {len(errors) - 10} more" if len(errors) > 10 else ""
        raise ValueError(f"mapping.json has {len(errors)} invalid rule(s):\n  {summary}{suffix}")

    logger.info(
        f"Loaded {len(character_result)} character rules, {len(spawn_result)} spawn rules, and "
        f"{len(zone_line_result)} zone line exclusions from {path}"
    )
    return character_result, spawn_result, zone_line_result


def _zone_line_error(rule: dict[str, object]) -> str | None:
    """Why a zone line rule is not a reviewed exclusion, or None when it is one."""
    unknown = sorted(rule.keys() - {"is_usable", "reason"})
    if unknown:
        return f"unknown fields {unknown}"
    if type(rule.get("is_usable")) is not int or rule["is_usable"] != 0:
        return "'is_usable' must be 0, because a rule can only exclude a line"
    reason = rule.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return "an exclusion requires a 'reason'"
    return None
