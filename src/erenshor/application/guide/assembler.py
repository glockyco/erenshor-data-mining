"""Quest guide assembler — builds QuestGuide entries from pre-fetched data.

Transforms a :class:`QuestDataContext` (all SQL data pre-fetched by the
repository layer) into a list of :class:`QuestGuide` entries.  Handles:

- Required item construction with unified ``ItemSource`` lists
- Trigger item injection for ``item_read`` quests
- Implicit prerequisite detection (quest-reward-only items)
- Quest type inference from completion methods
- Zone context inference from NPC locations
- Step auto-generation for simple quest types
- Rewards, chain links, and flags
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .schema import (
    AcquisitionSource,
    ChainLink,
    CompletionSource,
    Prerequisite,
    QuestFlags,
    QuestGuide,
    QuestStep,
    QuestType,
    RequiredItemInfo,
    Rewards,
)

if TYPE_CHECKING:
    import sqlite3

    from .repository import QuestDataContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def assemble_guides(ctx: QuestDataContext) -> list[QuestGuide]:
    """Build a QuestGuide for every quest in *ctx*.

    Level estimation is NOT performed here — the caller must run the
    levels module separately to fill in ``level_estimate`` on steps and
    guides.
    """
    guides: list[QuestGuide] = []
    for quest in ctx.quests:
        sk = quest["stable_key"]
        variant_rn = quest["resource_name"]

        acquisition = ctx.acquisition.get(sk, [])
        completion = ctx.completion.get(sk, [])

        required_items = _build_required_items(variant_rn, sk, ctx)
        _inject_trigger_items(sk, acquisition, required_items, ctx)
        implicit_prereqs = _detect_implicit_prerequisites(sk, required_items, ctx)

        # Merge explicit + implicit prerequisites, dedup by quest_key
        explicit_prereqs = ctx.prerequisites.get(sk, [])
        seen_keys: set[str] = {p.quest_key for p in explicit_prereqs}
        prerequisites = list(explicit_prereqs)
        for ip in implicit_prereqs:
            if ip.quest_key not in seen_keys:
                seen_keys.add(ip.quest_key)
                prerequisites.append(ip)

        quest_type = _infer_quest_type(completion, required_items)
        zone_context = _infer_zone_context(sk, acquisition, completion, ctx.npc_zones)

        steps = _generate_steps(
            quest_type,
            acquisition,
            completion,
            required_items,
            zone_context,
            ctx.quest_names,
            ctx.shout_keywords,
            sk,
        )

        rewards = _build_rewards(quest, ctx)
        chain = _build_chain(sk, ctx)
        flags = _build_flags(quest)

        guide = QuestGuide(
            db_name=quest["db_name"],
            stable_key=sk,
            display_name=quest["display_name"],
            description=quest["quest_desc"] or None,
            quest_type=quest_type,
            zone_context=zone_context,
            acquisition=acquisition,
            prerequisites=prerequisites,
            steps=steps,
            required_items=required_items,
            completion=completion,
            rewards=rewards,
            chain=chain,
            flags=flags,
            # level_estimate filled by levels.py
        )
        guides.append(guide)

    log.info("Assembled %d quest guides", len(guides))
    return guides


# ---------------------------------------------------------------------------
# Required items
# ---------------------------------------------------------------------------


def _build_required_items(
    variant_rn: str,
    quest_sk: str,
    ctx: QuestDataContext,
) -> list[RequiredItemInfo]:
    """Look up required items and attach unified sources, filtering self-refs."""
    items = ctx.required_items_map.get(variant_rn, [])
    result: list[RequiredItemInfo] = []
    for item in items:
        isk = item["item_stable_key"]
        # Filter out quest_reward sources that reference the quest itself —
        # a quest cannot be its own prerequisite.
        sources = [
            s for s in ctx.item_sources.get(isk, []) if not (s.type == "quest_reward" and s.quest_key == quest_sk)
        ]
        result.append(
            RequiredItemInfo(
                item_name=ctx.item_names.get(isk, isk),
                item_stable_key=isk,
                quantity=item["quantity"],
                sources=sources,
            )
        )
    return result


def _inject_trigger_items(
    quest_sk: str,
    acquisition: list[AcquisitionSource],
    required_items: list[RequiredItemInfo],
    ctx: QuestDataContext,
) -> None:
    """For item_read quests, add triggering items to *required_items*.

    When a quest has multiple item_read acquisition sources, they are
    alternative triggers -- the player only needs one.  All are injected
    with ``optional=True`` so the UI can show them as alternatives.
    When there is exactly one trigger, it is not marked optional since
    there is no alternative.
    """
    triggers = [a for a in acquisition if a.method == "item_read" and a.source_stable_key]
    if not triggers:
        return
    is_optional = len(triggers) > 1
    for acq in triggers:
        isk = acq.source_stable_key
        if any(ri.item_stable_key == isk for ri in required_items):
            continue
        sources = [
            s for s in ctx.item_sources.get(isk, []) if not (s.type == "quest_reward" and s.quest_key == quest_sk)
        ]
        required_items.append(
            RequiredItemInfo(
                item_name=ctx.item_names.get(isk, acq.source_name or isk),
                item_stable_key=isk,
                quantity=1,
                optional=is_optional,
                sources=sources,
            )
        )


def _detect_implicit_prerequisites(
    quest_sk: str,
    required_items: list[RequiredItemInfo],
    ctx: QuestDataContext,
) -> list[Prerequisite]:
    """Detect quests that are hard prerequisites via item dependency.

    If every source for a required item is ``quest_reward``, the rewarding
    quest(s) are implicit prerequisites — there is no other way to obtain
    the item.
    """
    result: list[Prerequisite] = []
    seen: set[str] = set()
    for ri in required_items:
        if not ri.sources:
            continue
        if all(s.type == "quest_reward" for s in ri.sources):
            for s in ri.sources:
                if s.quest_key and s.quest_key != quest_sk and s.quest_key not in seen:
                    seen.add(s.quest_key)
                    result.append(
                        Prerequisite(
                            type="quest",
                            quest_key=s.quest_key,
                            quest_name=ctx.quest_names.get(s.quest_key, s.name or s.quest_key),
                            item=ri.item_name,
                        )
                    )
    return result


# ---------------------------------------------------------------------------
# Quest type inference
# ---------------------------------------------------------------------------


def _infer_quest_type(
    completion: list[CompletionSource],
    required_items: list[RequiredItemInfo],
) -> str:
    """Infer quest type from completion methods and required items."""
    methods = {c.method for c in completion}

    if len(methods) == 0:
        return QuestType.SCRIPTED.value
    if len(methods) > 1 and "scripted" not in methods:
        return QuestType.HYBRID.value

    method = next(iter(methods))

    if method == "item_turnin" and required_items:
        return QuestType.FETCH.value

    method_to_type = {
        "item_turnin": QuestType.FETCH,
        "death": QuestType.KILL,
        "talk": QuestType.DIALOG,
        "zone": QuestType.ZONE_TRIGGER,
        "shout": QuestType.SHOUT,
        "read": QuestType.ITEM_READ,
        "scripted": QuestType.SCRIPTED,
        "chain": QuestType.CHAIN,
    }
    return method_to_type.get(method, QuestType.SCRIPTED).value


# ---------------------------------------------------------------------------
# Zone context inference
# ---------------------------------------------------------------------------


def _infer_zone_context(
    sk: str,
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
    npc_zones: dict[str, str],
) -> str | None:
    """Infer the primary zone from acquisition/completion NPC locations."""
    # Try acquisition NPC zones first (where you GET the quest)
    for acq in acquisition:
        if acq.source_stable_key and acq.source_type == "character":
            zone = npc_zones.get(acq.source_stable_key)
            if zone:
                return zone
        if acq.source_type == "zone" and acq.zone_name:
            return acq.zone_name

    # Then completion NPC zones
    for comp in completion:
        if comp.source_stable_key and comp.source_type == "character":
            zone = npc_zones.get(comp.source_stable_key)
            if zone:
                return zone
        if comp.source_type == "zone" and comp.zone_name:
            return comp.zone_name

    return None


# ---------------------------------------------------------------------------
# Rewards, chain, flags
# ---------------------------------------------------------------------------


def _build_rewards(quest: sqlite3.Row, ctx: QuestDataContext) -> Rewards:
    """Build rewards from quest row and context lookups."""
    sk = quest["stable_key"]
    variant_rn = quest["resource_name"]
    item_sk = quest["item_on_complete_stable_key"]
    next_sk = ctx.chain_next.get(sk)

    achievements: list[str] = []
    if quest["set_achievement_on_get"]:
        achievements.append(quest["set_achievement_on_get"])
    if quest["set_achievement_on_finish"]:
        achievements.append(quest["set_achievement_on_finish"])

    also_complete_sks = ctx.also_completes.get(variant_rn, [])
    also_complete_names = [ctx.quest_names.get(csk, csk) for csk in also_complete_sks]

    unlock_sk = quest["unlock_item_for_vendor_stable_key"]

    return Rewards(
        xp=quest["xp_on_complete"] or 0,
        gold=quest["gold_on_complete"] or 0,
        item_name=ctx.item_names.get(item_sk) if item_sk else None,
        item_stable_key=item_sk,
        next_quest_name=ctx.quest_names.get(next_sk) if next_sk else None,
        next_quest_stable_key=next_sk,
        also_completes=also_complete_names,
        vendor_unlock_item=ctx.item_names.get(unlock_sk) if unlock_sk else None,
        achievements=achievements,
        faction_effects=ctx.faction_effects.get(variant_rn, []),
    )


def _build_chain(sk: str, ctx: QuestDataContext) -> list[ChainLink]:
    """Build chain links from context lookups."""
    links: list[ChainLink] = []
    for prev_sk in ctx.chain_prev.get(sk, []):
        links.append(
            ChainLink(
                quest_name=ctx.quest_names.get(prev_sk, prev_sk),
                quest_stable_key=prev_sk,
                relationship="previous",
            )
        )
    next_sk = ctx.chain_next.get(sk)
    if next_sk:
        links.append(
            ChainLink(
                quest_name=ctx.quest_names.get(next_sk, next_sk),
                quest_stable_key=next_sk,
                relationship="next",
            )
        )
    for completer_sk in ctx.completed_by.get(sk, []):
        links.append(
            ChainLink(
                quest_name=ctx.quest_names.get(completer_sk, completer_sk),
                quest_stable_key=completer_sk,
                relationship="completed_by",
            )
        )
    return links


def _build_flags(quest: sqlite3.Row) -> QuestFlags:
    """Build flags from quest row."""
    return QuestFlags(
        repeatable=bool(quest["repeatable"]),
        disabled=bool(quest["disable_quest"]),
        disabled_text=quest["disable_text"] or None,
        kill_turn_in_holder=bool(quest["kill_turn_in_holder"]),
        destroy_turn_in_holder=bool(quest["destroy_turn_in_holder"]),
        drop_invuln_on_holder=bool(quest["drop_invuln_on_holder"]),
        once_per_spawn_instance=bool(quest["once_per_spawn_instance"]),
    )


# ---------------------------------------------------------------------------
# Step auto-generation
# ---------------------------------------------------------------------------


def _generate_steps(
    quest_type: str,
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
    required_items: list[RequiredItemInfo],
    zone_context: str | None,
    quest_names: dict[str, str],
    shout_keywords: dict[str, str],
    quest_sk: str,
) -> list[QuestStep]:
    """Auto-generate quest steps based on quest type and available data."""
    order = 0

    def step(action: str, description: str, **kwargs: object) -> QuestStep:
        nonlocal order
        order += 1
        return QuestStep(order=order, action=action, description=description, **kwargs)

    giver = _find_giver(acquisition)

    generators = {
        QuestType.FETCH.value: lambda: _steps_fetch(step, giver, required_items, completion, zone_context, acquisition),
        QuestType.KILL.value: lambda: _steps_kill(step, giver, completion),
        QuestType.DIALOG.value: lambda: _steps_dialog(step, giver, completion),
        QuestType.ZONE_TRIGGER.value: lambda: _steps_zone_trigger(step, giver, completion),
        QuestType.SHOUT.value: lambda: _steps_shout(step, giver, completion, shout_keywords),
        QuestType.ITEM_READ.value: lambda: _steps_item_read(step, acquisition, completion),
    }
    gen = generators.get(quest_type)
    # Scripted, chain, hybrid — can't auto-generate
    return gen() if gen else []


def _find_giver(acquisition: list[AcquisitionSource]) -> AcquisitionSource | None:
    """Find the primary quest giver (dialog NPC) from acquisition sources."""
    for acq in acquisition:
        if acq.method == "dialog":
            return acq
    return None


def _find_turnin_npc(completion: list[CompletionSource]) -> CompletionSource | None:
    """Find the turn-in NPC from completion sources."""
    for comp in completion:
        if comp.method == "item_turnin":
            return comp
    return None


# ---------------------------------------------------------------------------
# Step generators — one per quest type
# ---------------------------------------------------------------------------


def _steps_fetch(
    step,
    giver: AcquisitionSource | None,
    required_items: list[RequiredItemInfo],
    completion: list[CompletionSource],
    zone_context: str | None,
    acquisition: list[AcquisitionSource],
) -> list[QuestStep]:
    steps: list[QuestStep] = []

    # For item_read quests, generate read steps for all triggers
    item_read_acqs = [a for a in acquisition if a.method == "item_read" and a.source_name]
    if item_read_acqs:
        for acq in item_read_acqs:
            steps.append(
                step(
                    "read",
                    f"Obtain and read {acq.source_name}.",
                    target_name=acq.source_name,
                    target_type="item",
                )
            )
    elif giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
            )
        )

    for ri in required_items:
        if ri.optional:
            continue  # optional items are acquisition alternatives, not collect objectives
        desc = f"Collect {ri.item_name}"
        if ri.quantity > 1:
            desc = f"Collect {ri.quantity}x {ri.item_name}"
        steps.append(
            step(
                "collect",
                desc + ".",
                target_name=ri.item_name,
                target_type="item",
                quantity=ri.quantity,
            )
        )

    turnin_npc = _find_turnin_npc(completion)
    if turnin_npc:
        steps.append(
            step(
                "turn_in",
                f"Turn in items to {turnin_npc.source_name}.",
                target_name=turnin_npc.source_name,
                target_type="character",
                zone_name=turnin_npc.zone_name or zone_context,
            )
        )
    return steps


def _steps_kill(
    step,
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps: list[QuestStep] = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "death" and comp.source_name:
            steps.append(
                step(
                    "kill",
                    f"Defeat {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="character",
                    zone_name=comp.zone_name,
                )
            )
    return steps


def _steps_dialog(
    step,
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps: list[QuestStep] = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "talk" and comp.source_name:
            # Don't duplicate if completer is the same as giver
            if giver and comp.source_stable_key == giver.source_stable_key:
                continue
            steps.append(
                step(
                    "talk",
                    f"Speak to {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="character",
                    zone_name=comp.zone_name,
                )
            )
    return steps


def _steps_zone_trigger(
    step,
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps: list[QuestStep] = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "zone" and comp.source_name:
            steps.append(
                step(
                    "travel",
                    f"Travel to {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="zone",
                    zone_name=comp.source_name,
                )
            )
    return steps


def _steps_shout(
    step,
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
    shout_keywords: dict[str, str],
) -> list[QuestStep]:
    steps: list[QuestStep] = []
    if giver and giver.source_name:
        steps.append(
            step(
                "talk",
                f"Speak to {giver.source_name}.",
                target_name=giver.source_name,
                target_type="character",
                zone_name=giver.zone_name,
            )
        )
    for comp in completion:
        if comp.method == "shout" and comp.source_stable_key:
            keyword = shout_keywords.get(comp.source_stable_key, "")
            desc = f'Shout "{keyword}" near {comp.source_name}.' if keyword else f"Shout near {comp.source_name}."
            steps.append(
                step(
                    "shout",
                    desc,
                    target_name=comp.source_name,
                    target_type="character",
                    zone_name=comp.zone_name,
                    keyword=keyword or None,
                )
            )
    return steps


def _steps_item_read(
    step,
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps: list[QuestStep] = []
    # Generate a read step for each item_read trigger
    triggers = [a for a in acquisition if a.method == "item_read" and a.source_name]
    for acq in triggers:
        steps.append(
            step(
                "read",
                f"Obtain and read {acq.source_name}.",
                target_name=acq.source_name,
                target_type="item",
            )
        )

    # Remaining steps from completion sources
    for comp in completion:
        if comp.method == "read" and comp.source_name:
            # Don't duplicate the starting item read step
            if any(s.target_name == comp.source_name for s in steps):
                continue
            steps.append(
                step(
                    "read",
                    f"Read {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="item",
                )
            )
    return steps
