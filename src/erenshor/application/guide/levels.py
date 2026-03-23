"""Quest guide level estimation.

Computes per-step and per-quest level estimates, then propagates levels
through quest-reward item dependencies via topological sort.

All data comes from :class:`QuestDataContext` — no SQL queries here.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import QuestDataContext
from .schema import (
    LevelEstimate,
    LevelFactor,
    QuestGuide,
    QuestStep,
    RequiredItemInfo,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_levels(guides: list[QuestGuide], ctx: QuestDataContext) -> None:
    """Attach :class:`LevelEstimate` to every step and quest, in-place.

    1. Topologically sort quests so quest-reward levels flow forward.
    2. Compute step levels → quest level in dependency order.
    3. Backfill quest-reward ``ItemSource.level`` from rewarding quests.
    4. Recompute steps that consumed quest-reward sources (levels now populated).
    """
    guide_by_key = {g.stable_key: g for g in guides}
    topo_order = _topological_order(guides)

    # Phase 1: compute levels in dependency order
    for sk in topo_order:
        guide = guide_by_key.get(sk)
        if guide is None:
            continue
        _compute_guide_levels(guide, ctx)

    # Phase 2: propagate quest levels into quest_reward ItemSource.level
    _propagate_quest_reward_levels(guides, guide_by_key)

    # Phase 3: recompute steps that have quest_reward sources whose levels
    # may have changed after propagation
    for guide in guides:
        if _has_quest_reward_sources(guide):
            _compute_guide_levels(guide, ctx)


# ---------------------------------------------------------------------------
# Per-guide level computation
# ---------------------------------------------------------------------------


def _compute_guide_levels(guide: QuestGuide, ctx: QuestDataContext) -> None:
    """Compute step-level and quest-level estimates for a single guide."""
    for step in guide.steps:
        step.level_estimate = _compute_step_level(step, guide.required_items, ctx)
    guide.level_estimate = _compute_quest_level(guide.steps)


# ---------------------------------------------------------------------------
# Step-level estimation
# ---------------------------------------------------------------------------


def _compute_step_level(
    step: QuestStep,
    required_items: list[RequiredItemInfo],
    ctx: QuestDataContext,
) -> LevelEstimate | None:
    """Estimate the recommended level for a single quest step.

    - collect/read: min level across all item sources with a known level.
    - talk/turn_in/shout: zone median of the lowest-level zone the NPC spawns in.
    - travel: zone median of the destination zone.
    """
    factors: list[LevelFactor] = []

    if step.action in ("talk", "turn_in", "shout"):
        _add_npc_zone_factor(step.target_name, ctx, factors)

    elif step.action == "travel":
        zone_name = step.zone_name or step.target_name
        if zone_name:
            zi = ctx.zone_by_display.get(zone_name)
            if zi and zi.level_median is not None:
                factors.append(LevelFactor(source="zone_median", name=zone_name, level=zi.level_median))

    elif step.action in ("collect", "read") and step.target_name:
        item = next(
            (ri for ri in required_items if ri.item_name.lower() == step.target_name.lower()),
            None,
        )
        if item:
            _add_item_source_factors(item, factors)

    if not factors:
        return None

    # Deduplicate factors by (source, name, level)
    seen: set[tuple[str, str | None, int]] = set()
    unique: list[LevelFactor] = []
    for f in factors:
        key = (f.source, f.name, f.level)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    recommended = min(f.level for f in unique)
    return LevelEstimate(recommended=recommended, factors=unique)


# ---------------------------------------------------------------------------
# Quest-level estimation
# ---------------------------------------------------------------------------


def _compute_quest_level(steps: list[QuestStep]) -> LevelEstimate | None:
    """Quest level = max of effective per-step levels.

    Required steps (``or_group is None``) contribute their level directly.
    Consecutive steps sharing the same ``or_group`` are alternatives —
    only the minimum level in each group counts, since the player only
    needs to complete one.
    """
    effective: list[tuple[QuestStep, int]] = []
    or_group_buf: list[tuple[QuestStep, int]] = []
    current_group: str | None = None

    def flush_group() -> None:
        if or_group_buf:
            best = min(or_group_buf, key=lambda t: t[1])
            effective.append(best)
            or_group_buf.clear()

    for step in steps:
        if step.level_estimate is None or step.level_estimate.recommended is None:
            continue
        if step.or_group is not None:
            if step.or_group != current_group:
                flush_group()
                current_group = step.or_group
            or_group_buf.append((step, step.level_estimate.recommended))
        else:
            flush_group()
            current_group = None
            effective.append((step, step.level_estimate.recommended))

    flush_group()

    if not effective:
        return None

    max_step, max_level = max(effective, key=lambda t: t[1])
    return LevelEstimate(
        recommended=max_level,
        factors=[
            LevelFactor(
                source=f"step_{max_step.order}",
                name=max_step.description,
                level=max_level,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Factor helpers
# ---------------------------------------------------------------------------


def _add_npc_zone_factor(
    npc_name: str | None,
    ctx: QuestDataContext,
    factors: list[LevelFactor],
) -> None:
    """Add a zone-median factor for the lowest-level zone an NPC spawns in."""
    if not npc_name:
        return
    zones = ctx.char_name_zones.get(npc_name)
    if not zones:
        return

    best_zi = None
    for zone_display in zones:
        zi = ctx.zone_by_display.get(zone_display)
        if (
            zi
            and zi.level_median is not None
            and (best_zi is None or best_zi.level_median is None or zi.level_median < best_zi.level_median)
        ):
            best_zi = zi

    if best_zi and best_zi.level_median is not None:
        factors.append(LevelFactor(source="zone_median", name=best_zi.display_name, level=best_zi.level_median))


def _add_item_source_factors(
    item: RequiredItemInfo,
    factors: list[LevelFactor],
) -> None:
    """Add one factor per item source that has a known level.

    In v3 all source types are unified into ItemSource with inline level.
    The factor source/name comes directly from the ItemSource fields.
    """
    for src in item.sources:
        if src.level is not None:
            factors.append(
                LevelFactor(
                    source=src.type,
                    name=src.name or src.zone,
                    level=src.level,
                )
            )


# ---------------------------------------------------------------------------
# Quest-reward level propagation
# ---------------------------------------------------------------------------


def _propagate_quest_reward_levels(
    guides: list[QuestGuide],
    guide_by_key: dict[str, QuestGuide],
) -> None:
    """Set ``ItemSource.level`` on quest_reward sources from the rewarding quest's level."""
    for guide in guides:
        for item in guide.required_items:
            for src in item.sources:
                if src.type == "quest_reward" and src.quest_key:
                    rewarding = guide_by_key.get(src.quest_key)
                    if rewarding and rewarding.level_estimate and rewarding.level_estimate.recommended is not None:
                        src.level = rewarding.level_estimate.recommended


def _has_quest_reward_sources(guide: QuestGuide) -> bool:
    """Check if any required item has a quest_reward source."""
    return any(src.type == "quest_reward" for item in guide.required_items for src in item.sources)


# ---------------------------------------------------------------------------
# Topological ordering
# ---------------------------------------------------------------------------


def _topological_order(guides: list[QuestGuide]) -> list[str]:
    """Topologically sort quests by quest-reward dependencies (Kahn's algorithm).

    Edge: guide.stable_key depends on src.quest_key when a required item
    has a quest_reward source. The rewarding quest must be processed first.

    Returns stable_keys in processing order. Cyclic quests are appended
    last with a warning.
    """
    all_keys = {g.stable_key for g in guides}

    # in_degree[sk] = number of quest-reward dependencies
    in_degree: dict[str, int] = {g.stable_key: 0 for g in guides}
    # dependents[sk] = quests that depend on sk being computed first
    dependents: dict[str, list[str]] = defaultdict(list)

    for guide in guides:
        seen_deps: set[str] = set()
        for item in guide.required_items:
            for src in item.sources:
                if src.type == "quest_reward" and src.quest_key and src.quest_key in all_keys:
                    dep_key = src.quest_key
                    if dep_key != guide.stable_key and dep_key not in seen_deps:
                        seen_deps.add(dep_key)
                        in_degree[guide.stable_key] += 1
                        dependents[dep_key].append(guide.stable_key)

    # Kahn's algorithm
    queue: deque[str] = deque(sk for sk, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while queue:
        sk = queue.popleft()
        result.append(sk)
        for dependent in dependents.get(sk, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Cycle detection: any quest not yet in result is part of a cycle
    if len(result) < len(guides):
        cyclic = [g.stable_key for g in guides if g.stable_key not in set(result)]
        log.warning(
            "Quest-reward dependency cycle detected among %d quests: %s. "
            "Processing without quest-reward level contribution.",
            len(cyclic),
            ", ".join(cyclic[:10]),
        )
        result.extend(cyclic)

    return result
