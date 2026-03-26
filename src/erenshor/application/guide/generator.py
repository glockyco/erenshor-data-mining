"""Quest guide generator — thin orchestrator.

Delegates to repository (data loading), assembler (guide construction),
levels (level estimation), and serializer (JSON output).
"""

from __future__ import annotations

from pathlib import Path

from .schema import GuideOutput, ItemSource, QuestGuide, QuestStep
from .serializer import guides_to_json

__all__ = ["generate", "guides_to_json"]


def generate(db_path: Path) -> GuideOutput:
    """Load quest data, assemble guides, compute levels, return v3 output."""
    from .assembler import assemble_guides
    from .levels import compute_levels
    from .repository import load_quest_data, materialize_sub_trees

    ctx = load_quest_data(db_path)
    guides = assemble_guides(ctx)
    compute_levels(guides, ctx)
    _sort_item_sources(guides)
    _sort_or_groups(guides)
    materialize_sub_trees(guides, ctx)
    return GuideOutput(
        version=5,
        zone_lookup=ctx.zone_lookup,
        character_spawns=ctx.character_spawns,
        zone_lines=ctx.zone_lines,
        chain_groups=ctx.chain_groups,
        character_quest_unlocks=ctx.character_quest_unlocks,
        quests=guides,
    )


def _sort_item_sources(guides: list[QuestGuide]) -> None:
    """Sort each required item's sources by level ascending (None last).

    Called after compute_levels so all source levels are final.
    """

    def _key(src: ItemSource) -> tuple[int, int]:
        if src.level is not None:
            return (0, src.level)
        return (1, 0)

    for guide in guides:
        for item in guide.required_items:
            item.sources.sort(key=_key)


def _sort_or_groups(guides: list[QuestGuide]) -> None:
    """Sort steps within each or_group by level (lowest first).

    Within a group of consecutive steps sharing the same or_group,
    reorder so the lowest-level alternative appears first. This puts
    the most accessible option at the top of the UI.
    """
    for guide in guides:
        if not guide.steps:
            continue
        guide.steps = _sort_steps(guide.steps)


def _sort_steps(steps: list[QuestStep]) -> list[QuestStep]:
    """Collect consecutive or_group runs, sort each by level, reassign order."""
    result: list[QuestStep] = []
    group: list[QuestStep] = []
    group_name: str | None = None

    def _flush(grp: list[QuestStep], out: list[QuestStep]) -> None:
        if grp:
            grp.sort(
                key=lambda s: (
                    s.level_estimate.recommended if s.level_estimate and s.level_estimate.recommended else 999
                )
            )
            out.extend(grp)

    for step in steps:
        if step.or_group is not None and step.or_group == group_name:
            group.append(step)
        else:
            _flush(group, result)
            group = []
            group_name = step.or_group
            if step.or_group:
                group.append(step)
            else:
                result.append(step)

    _flush(group, result)

    for i, step in enumerate(result):
        step.order = i + 1
    return result
