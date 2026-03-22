"""Quest guide merge and curation report.

Merges auto-generated quest guide data with a manual curation layer.
Produces a curation report identifying quests that need human attention.

Manual layer files live in quest_guides/manual/{db_name}.json and contain
sparse overrides. Only fields present in the manual file replace auto values.
For array fields (steps, tags, tips), the manual layer replaces the entire
array -- no partial array merging.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from .generator import guides_to_json

if TYPE_CHECKING:
    from .schema import QuestGuide


def merge_guides(
    auto_guides: list[QuestGuide],
    manual_dir: Path | None,
) -> list[dict[str, Any]]:
    """Merge auto-generated guides with manual overrides.

    Args:
        auto_guides: Auto-generated QuestGuide entries.
        manual_dir: Directory containing manual override JSON files.
            Each file is named {db_name}.json. If None, no merging occurs.

    Returns:
        List of merged guide dicts ready for JSON serialization.
    """
    auto_dicts = guides_to_json(auto_guides)

    if manual_dir is None or not manual_dir.exists():
        return auto_dicts

    # Index auto guides by db_name for O(1) lookup
    auto_by_name = {d["db_name"]: d for d in auto_dicts}

    manual_count = 0
    for manual_file in sorted(manual_dir.glob("*.json")):
        try:
            manual_data = json.loads(manual_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping invalid manual file {manual_file.name}: {e}")
            continue

        db_name = manual_data.get("db_name") or manual_file.stem
        if db_name not in auto_by_name:
            logger.warning(f"Manual file {manual_file.name} has no matching quest (db_name={db_name})")
            continue

        auto_dict = auto_by_name[db_name]
        _apply_overrides(auto_dict, manual_data)
        manual_count += 1

    if manual_count:
        logger.info(f"Applied {manual_count} manual overrides")

    return list(auto_by_name.values())


def _apply_overrides(auto: dict[str, Any], manual: dict[str, Any]) -> None:
    """Apply manual overrides onto auto dict. Manual wins for all present fields."""
    for key, value in manual.items():
        if key.startswith("_") or key == "db_name":
            continue
        auto[key] = value


# ---------------------------------------------------------------------------
# Curation report
# ---------------------------------------------------------------------------


def generate_curation_report(guides: list[dict[str, Any]]) -> str:
    """Generate a human-readable curation report.

    Identifies quests needing manual attention:
    - No steps (scripted/chain/hybrid quests)
    - No acquisition source
    - No completion source
    - Missing zone context
    """
    lines: list[str] = []
    lines.append("# Quest Guide Curation Report")
    lines.append("")

    # Categorize
    no_steps: list[dict[str, Any]] = []
    no_acquisition: list[dict[str, Any]] = []
    no_completion: list[dict[str, Any]] = []
    no_zone: list[dict[str, Any]] = []

    for g in guides:
        if not g.get("steps"):
            no_steps.append(g)
        if not g.get("acquisition"):
            no_acquisition.append(g)
        if not g.get("completion"):
            no_completion.append(g)
        if not g.get("zone_context"):
            no_zone.append(g)

    # Summary
    total = len(guides)
    with_steps = total - len(no_steps)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total quests**: {total}")
    lines.append(f"- **With auto-generated steps**: {with_steps} ({100 * with_steps // total}%)")
    lines.append(f"- **Needing step curation**: {len(no_steps)}")
    lines.append(f"- **No known acquisition source**: {len(no_acquisition)}")
    lines.append(f"- **No known completion source**: {len(no_completion)}")
    lines.append(f"- **No zone context**: {len(no_zone)}")
    lines.append("")

    # Quest type breakdown
    type_counts: dict[str, int] = {}
    type_with_steps: dict[str, int] = {}
    for g in guides:
        qt = g.get("quest_type", "unknown")
        type_counts[qt] = type_counts.get(qt, 0) + 1
        if g.get("steps"):
            type_with_steps[qt] = type_with_steps.get(qt, 0) + 1

    lines.append("## By Quest Type")
    lines.append("")
    lines.append("| Type | Total | With Steps | Needs Curation |")
    lines.append("|------|-------|------------|----------------|")
    for qt in sorted(type_counts.keys()):
        total_qt = type_counts[qt]
        with_s = type_with_steps.get(qt, 0)
        needs = total_qt - with_s
        lines.append(f"| {qt} | {total_qt} | {with_s} | {needs} |")
    lines.append("")

    # Quests needing steps
    if no_steps:
        lines.append("## Quests Needing Step Curation")
        lines.append("")
        for g in sorted(no_steps, key=lambda x: x.get("display_name", "")):
            qt = g.get("quest_type", "unknown")
            name = g.get("display_name", g["db_name"])
            lines.append(f"- **{name}** ({g['db_name']}) -- type: {qt}")
        lines.append("")

    # Quests with no acquisition source
    if no_acquisition:
        lines.append("## Quests With No Known Acquisition Source")
        lines.append("")
        for g in sorted(no_acquisition, key=lambda x: x.get("display_name", "")):
            name = g.get("display_name", g["db_name"])
            lines.append(f"- **{name}** ({g['db_name']})")
        lines.append("")

    return "\n".join(lines)
