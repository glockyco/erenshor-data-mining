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
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .schema import (
    AcceptanceMode,
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
    StepAction,
    UnlockedCharacter,
    UnlockedZoneLine,
    VendorUnlockInfo,
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
    # Build reverse indexes: quest_db_name → what completing it unlocks
    zone_line_unlocks = _build_zone_line_unlock_index(ctx)
    character_unlocks = _build_character_unlock_index(ctx)

    guides: list[QuestGuide] = []
    for quest in ctx.quests:
        sk = quest["stable_key"]
        variant_rn = quest["resource_name"]

        acquisition = ctx.acquisition.get(sk, [])
        completion = ctx.completion.get(sk, [])

        required_items = _build_required_items(variant_rn, sk, ctx)
        _inject_readable_items(sk, acquisition, completion, required_items, ctx)
        implicit_prereqs = _detect_implicit_prerequisites(sk, required_items, ctx)
        implicit_prereqs += _detect_character_unlock_prerequisites(sk, acquisition, completion, ctx)

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

        rewards = _build_rewards(quest, ctx, zone_line_unlocks, character_unlocks)
        chain = _build_chain(sk, ctx)
        flags = _build_flags(quest)

        guide = QuestGuide(
            db_name=quest["db_name"],
            stable_key=sk,
            display_name=quest["display_name"],
            description=quest["quest_desc"] or None,
            quest_type=quest_type,
            acceptance=AcceptanceMode.IMPLICIT if not acquisition else AcceptanceMode.EXPLICIT,
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


def _inject_readable_items(
    quest_sk: str,
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
    required_items: list[RequiredItemInfo],
    ctx: QuestDataContext,
) -> None:
    """Inject items the player must obtain and read into *required_items*.

    Covers two cases:
    - item_read acquisition triggers (reading an item starts the quest)
    - read completion sources (reading an item completes the quest)

    When multiple readable items exist, they are alternatives (or_group="read").
    Mutates *required_items* in place.
    """
    # Collect all readable item stable keys from both acquisition and completion
    readable: list[tuple[str, str]] = []  # (stable_key, display_name)
    for acq in acquisition:
        if acq.method == "item_read" and acq.source_stable_key:
            readable.append((acq.source_stable_key, acq.source_name or acq.source_stable_key))
    for comp in completion:
        if (
            comp.method == "read"
            and comp.source_stable_key
            and not any(sk == comp.source_stable_key for sk, _ in readable)
        ):
            readable.append((comp.source_stable_key, comp.source_name or comp.source_stable_key))

    if not readable:
        return

    is_optional = len(readable) > 1
    for isk, name in readable:
        if any(ri.item_stable_key == isk for ri in required_items):
            continue
        sources = [
            s for s in ctx.item_sources.get(isk, []) if not (s.type == "quest_reward" and s.quest_key == quest_sk)
        ]
        required_items.append(
            RequiredItemInfo(
                item_name=ctx.item_names.get(isk, name),
                item_stable_key=isk,
                quantity=1,
                or_group="read" if is_optional else None,
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


def _detect_character_unlock_prerequisites(
    quest_sk: str,
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
    ctx: QuestDataContext,
) -> list[Prerequisite]:
    """Detect prerequisites from quest-gated character spawning.

    If any character involved in the quest (as giver or completer) only spawns
    after another quest is completed, that quest is an implicit prerequisite.
    Checks both acquisition and completion sources so that implicit quests with
    no explicit giver (like MEETBASSLE, where Bassle is completer only) are also
    handled correctly.
    """
    result: list[Prerequisite] = []
    seen: set[str] = set()

    # Collect (stable_key, display_name) for all character sources.
    # Both AcquisitionSource and CompletionSource have source_stable_key /
    # source_name; using attribute access works for both types.
    all_sources = [
        (src.source_stable_key, src.source_name) for src in (*acquisition, *completion) if src.source_stable_key
    ]

    for char_key, source_name in all_sources:
        groups = ctx.character_quest_unlocks.get(char_key)
        if not groups:
            continue
        # Each group is an AND list; any group sufficing means OR.
        # For prerequisites, take the smallest group (fewest quests needed).
        smallest = min(groups, key=len)
        for quest_db_name in smallest:
            prereq_sk = f"quest:{quest_db_name.lower()}"
            if prereq_sk == quest_sk or prereq_sk in seen:
                continue
            seen.add(prereq_sk)
            result.append(
                Prerequisite(
                    type="quest",
                    quest_key=prereq_sk,
                    quest_name=ctx.quest_names.get(prereq_sk, quest_db_name),
                    note=f"{source_name} spawns after quest completion",
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
        return QuestType.UNKNOWN.value
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
        "scripted": QuestType.UNKNOWN,
        "chain": QuestType.CHAIN,
    }
    return method_to_type.get(method, QuestType.UNKNOWN).value


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


def _build_zone_line_unlock_index(
    ctx: QuestDataContext,
) -> dict[str, list[UnlockedZoneLine]]:
    """Invert zone line unlock groups into quest_db_name → unlocked zone lines.

    For AND groups (multiple quests needed), each quest gets the zone line
    with co_requirements listing the other quests in the group. When the
    same destination appears via multiple OR groups, keep the entry with
    the fewest co-requirements (the easiest path).
    """
    # Collect all (quest_db, to_zone) → best entry (fewest co-reqs)
    best: dict[tuple[str, str], UnlockedZoneLine] = {}
    for zl in ctx.zone_lines:
        if not zl.required_quest_groups:
            continue
        from_zone = ctx.zone_lookup.get(zl.scene, None)
        from_display = from_zone.display_name if from_zone else zl.scene
        to_display = zl.destination_display or zl.destination_zone_key
        for group in zl.required_quest_groups:
            for quest_db in group:
                co_reqs = [q for q in group if q != quest_db]
                key = (quest_db, to_display)
                if key not in best or len(co_reqs) < len(best[key].co_requirements):
                    best[key] = UnlockedZoneLine(
                        from_zone=from_display,
                        to_zone=to_display,
                        co_requirements=co_reqs,
                    )

    result: dict[str, list[UnlockedZoneLine]] = {}
    for (quest_db, _), entry in best.items():
        result.setdefault(quest_db, []).append(entry)
    return result


def _build_character_unlock_index(
    ctx: QuestDataContext,
) -> dict[str, list[UnlockedCharacter]]:
    """Invert character quest unlocks into quest_db_name → unlocked characters.

    Deduplicates by (quest_db_name, character_name) across OR groups.
    """
    seen: set[tuple[str, str]] = set()
    result: dict[str, list[UnlockedCharacter]] = {}
    for char_sk, groups in ctx.character_quest_unlocks.items():
        info = ctx.char_display_info.get(char_sk)
        if not info:
            continue
        name, zone = info
        for group in groups:
            for quest_db in group:
                key = (quest_db, name)
                if key in seen:
                    continue
                seen.add(key)
                result.setdefault(quest_db, []).append(UnlockedCharacter(name=name, zone=zone))
    return result


def _build_rewards(
    quest: sqlite3.Row,
    ctx: QuestDataContext,
    zone_line_unlocks: dict[str, list[UnlockedZoneLine]],
    character_unlocks: dict[str, list[UnlockedCharacter]],
) -> Rewards:
    """Build rewards from quest row and context lookups."""
    sk = quest["stable_key"]
    db_name = quest["db_name"]
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

    vendor_unlock: VendorUnlockInfo | None = None
    vqu = ctx.vendor_quest_unlocks.get(sk)
    if vqu:
        vendor_unlock = VendorUnlockInfo(item_name=vqu.item_name, vendor_name=vqu.vendor_name)

    return Rewards(
        xp=quest["xp_on_complete"] or 0,
        gold=quest["gold_on_complete"] or 0,
        item_name=ctx.item_names.get(item_sk) if item_sk else None,
        item_stable_key=item_sk,
        next_quest_name=ctx.quest_names.get(next_sk) if next_sk else None,
        next_quest_stable_key=next_sk,
        also_completes=also_complete_names,
        vendor_unlock=vendor_unlock,
        unlocked_zone_lines=zone_line_unlocks.get(db_name, []),
        unlocked_characters=character_unlocks.get(db_name, []),
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

    def step(action: str, description: str, **kwargs: Any) -> QuestStep:
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
        QuestType.HYBRID.value: lambda: _steps_hybrid(
            step,
            giver,
            completion,
            required_items,
            zone_context,
            shout_keywords,
        ),
        QuestType.CHAIN.value: lambda: _steps_hybrid(
            step,
            giver,
            completion,
            required_items,
            zone_context,
            shout_keywords,
        ),
    }
    generators[QuestType.UNKNOWN.value] = lambda: _steps_unknown(step, giver, required_items)
    gen = generators.get(quest_type)
    return gen() if gen else []


def _talk_description(npc_name: str, keyword: str | None = None) -> str:
    """Build a step description for talking to an NPC.

    When a keyword is required, the description tells the player what to say.
    """
    if keyword:
        return f'Say "{keyword}" to {npc_name}.'
    return f"Speak to {npc_name}."


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
# Shared step emitters
# ---------------------------------------------------------------------------


def _emit_giver_step(
    step: Callable[..., QuestStep],
    giver: AcquisitionSource | None,
) -> list[QuestStep]:
    """Emit the acquisition step (talk to quest giver) if applicable."""
    if giver and giver.source_name:
        return [
            step(
                "talk",
                _talk_description(giver.source_name, giver.keyword),
                target_name=giver.source_name,
                target_type="character",
                target_key=giver.source_stable_key,
                zone_name=giver.zone_name,
                keyword=giver.keyword or None,
            )
        ]
    return []


def _emit_collect_steps(
    step: Callable[..., QuestStep],
    required_items: list[RequiredItemInfo],
) -> list[QuestStep]:
    """Emit collect steps for required items.

    Items with ``or_group`` set are acquisition alternatives (e.g. multiple
    sources for the same quest item), not separate collect objectives.
    """
    steps: list[QuestStep] = []
    for ri in required_items:
        if ri.or_group is not None:
            continue
        desc = f"Collect {ri.quantity}x {ri.item_name}" if ri.quantity > 1 else f"Collect {ri.item_name}"
        steps.append(
            step(
                "collect",
                desc + ".",
                target_name=ri.item_name,
                target_type="item",
                target_key=ri.item_stable_key,
                quantity=ri.quantity,
            )
        )
    return steps


def _emit_completion_step(
    step: Callable[..., QuestStep],
    comp: CompletionSource,
    shout_keywords: dict[str, str],
    giver: AcquisitionSource | None = None,
    zone_context: str | None = None,
    or_group: str | None = None,
) -> QuestStep | None:
    """Emit a single completion step, dispatching by method.

    Returns None when the source can't produce a step (missing data, or
    the completer is the same NPC as the giver).
    """
    handlers: dict[str, Callable[..., QuestStep | None]] = {
        "talk": lambda: _comp_talk(step, comp, giver, or_group),
        "death": lambda: _comp_character(step, comp, "kill", "Defeat", or_group),
        "zone": lambda: _comp_zone(step, comp, or_group),
        "shout": lambda: _comp_shout(step, comp, shout_keywords, or_group),
        "item_turnin": lambda: _comp_character(
            step,
            comp,
            "turn_in",
            "Turn in items to",
            or_group,
            zone_context,
        ),
        "read": lambda: _comp_read(step, comp, or_group),
        "chain": lambda: _comp_chain(step, comp, or_group),
    }
    handler = handlers.get(comp.method)
    return handler() if handler else None


def _comp_talk(
    step: Callable[..., QuestStep],
    comp: CompletionSource,
    giver: AcquisitionSource | None,
    or_group: str | None,
) -> QuestStep | None:
    if not comp.source_name:
        return None
    if giver and comp.source_stable_key == giver.source_stable_key:
        return None
    return step(
        "talk",
        _talk_description(comp.source_name, comp.keyword),
        target_name=comp.source_name,
        target_type="character",
        target_key=comp.source_stable_key,
        zone_name=comp.zone_name,
        keyword=comp.keyword or None,
        or_group=or_group,
    )


def _comp_character(
    step: Callable[..., QuestStep],
    comp: CompletionSource,
    action: str,
    verb: str,
    or_group: str | None,
    zone_context: str | None = None,
) -> QuestStep | None:
    if not comp.source_name:
        return None
    return step(
        action,
        f"{verb} {comp.source_name}.",
        target_name=comp.source_name,
        target_type="character",
        target_key=comp.source_stable_key,
        zone_name=comp.zone_name or zone_context,
        or_group=or_group,
    )


def _comp_zone(
    step: Callable[..., QuestStep],
    comp: CompletionSource,
    or_group: str | None,
) -> QuestStep | None:
    if not comp.source_name:
        return None
    return step(
        "travel",
        f"Travel to {comp.source_name}.",
        target_name=comp.source_name,
        target_type="zone",
        target_key=comp.source_stable_key,
        zone_name=comp.source_name,
        or_group=or_group,
    )


def _comp_shout(
    step: Callable[..., QuestStep],
    comp: CompletionSource,
    shout_keywords: dict[str, str],
    or_group: str | None,
) -> QuestStep | None:
    if not comp.source_stable_key:
        return None
    keyword = shout_keywords.get(comp.source_stable_key, "")
    desc = f'Shout "{keyword}" near {comp.source_name}.' if keyword else f"Shout near {comp.source_name}."
    return step(
        "shout",
        desc,
        target_name=comp.source_name,
        target_type="character",
        target_key=comp.source_stable_key,
        zone_name=comp.zone_name,
        keyword=keyword or None,
        or_group=or_group,
    )


def _comp_read(
    step: Callable[..., QuestStep],
    comp: CompletionSource,
    or_group: str | None,
) -> QuestStep | None:
    if not comp.source_name:
        return None
    return step(
        "read",
        f"Read {comp.source_name}.",
        target_name=comp.source_name,
        target_type="item",
        target_key=comp.source_stable_key,
        or_group=or_group,
    )


def _comp_chain(
    step: Callable[..., QuestStep],
    comp: CompletionSource,
    or_group: str | None,
) -> QuestStep | None:
    if not comp.source_name:
        return None
    return step(
        "complete_quest",
        f"Complete {comp.source_name}.",
        target_name=comp.source_name,
        target_type="quest",
        target_key=comp.source_stable_key,
        or_group=or_group,
    )


# ---------------------------------------------------------------------------
# Step generators — one per quest type
# ---------------------------------------------------------------------------


def _steps_unknown(
    step: Callable[..., QuestStep],
    giver: AcquisitionSource | None,
    required_items: list[RequiredItemInfo],
) -> list[QuestStep]:
    """Generate whatever steps are known for a quest with unknown completion.

    Emits the giver and any collect steps from available data, then always
    appends a terminal note that completion conditions are not yet known.
    """
    steps: list[QuestStep] = []
    steps.extend(_emit_giver_step(step, giver))
    steps.extend(_emit_collect_steps(step, required_items))
    steps.append(
        step(
            StepAction.CUSTOM.value,
            "How to complete this quest is not yet known. It may not be fully "
            "implemented in the current game version, or our guide data may be "
            "incomplete.",
        )
    )
    return steps


def _steps_fetch(
    step: Callable[..., QuestStep],
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
        is_optional = len(item_read_acqs) > 1
        for acq in item_read_acqs:
            steps.append(
                step(
                    "read",
                    f"Obtain and read {acq.source_name}.",
                    target_name=acq.source_name,
                    target_type="item",
                    target_key=acq.source_stable_key,
                    or_group="read" if is_optional else None,
                )
            )
    else:
        steps.extend(_emit_giver_step(step, giver))

    steps.extend(_emit_collect_steps(step, required_items))

    turnin_npc = _find_turnin_npc(completion)
    if turnin_npc:
        steps.append(
            step(
                "turn_in",
                f"Turn in items to {turnin_npc.source_name}.",
                target_name=turnin_npc.source_name,
                target_type="character",
                target_key=turnin_npc.source_stable_key,
                zone_name=turnin_npc.zone_name or zone_context,
            )
        )
    return steps


def _steps_kill(
    step: Callable[..., QuestStep],
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps = _emit_giver_step(step, giver)
    for comp in completion:
        if comp.method == "death" and comp.source_name:
            steps.append(
                step(
                    "kill",
                    f"Defeat {comp.source_name}.",
                    target_name=comp.source_name,
                    target_type="character",
                    target_key=comp.source_stable_key,
                    zone_name=comp.zone_name,
                )
            )
    return steps


def _steps_dialog(
    step: Callable[..., QuestStep],
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps = _emit_giver_step(step, giver)
    for comp in completion:
        if comp.method == "talk" and comp.source_name:
            # Don't duplicate if completer is the same as giver
            if giver and comp.source_stable_key == giver.source_stable_key:
                continue
            steps.append(
                step(
                    "talk",
                    _talk_description(comp.source_name, comp.keyword),
                    target_name=comp.source_name,
                    target_type="character",
                    target_key=comp.source_stable_key,
                    zone_name=comp.zone_name,
                    keyword=comp.keyword or None,
                )
            )
    return steps


def _steps_zone_trigger(
    step: Callable[..., QuestStep],
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps = _emit_giver_step(step, giver)
    zone_comps = [c for c in completion if c.method == "zone" and c.source_name]
    is_zone_optional = len(zone_comps) > 1
    for comp in zone_comps:
        steps.append(
            step(
                "travel",
                f"Travel to {comp.source_name}.",
                target_name=comp.source_name,
                target_type="zone",
                target_key=comp.source_stable_key,
                zone_name=comp.source_name,
                or_group="zone" if is_zone_optional else None,
            )
        )
    return steps


def _steps_shout(
    step: Callable[..., QuestStep],
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
    shout_keywords: dict[str, str],
) -> list[QuestStep]:
    steps = _emit_giver_step(step, giver)
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
                    target_key=comp.source_stable_key,
                    zone_name=comp.zone_name,
                    keyword=keyword or None,
                )
            )
    return steps


def _steps_item_read(
    step: Callable[..., QuestStep],
    acquisition: list[AcquisitionSource],
    completion: list[CompletionSource],
) -> list[QuestStep]:
    steps: list[QuestStep] = []
    # Generate a read step for each item_read trigger
    triggers = [a for a in acquisition if a.method == "item_read" and a.source_name]
    is_optional = len(triggers) > 1
    for acq in triggers:
        steps.append(
            step(
                "read",
                f"Obtain and read {acq.source_name}.",
                target_name=acq.source_name,
                target_type="item",
                target_key=acq.source_stable_key,
                or_group="read" if is_optional else None,
            )
        )

    # Remaining steps from completion sources
    read_comps = [c for c in completion if c.method == "read" and c.source_name]
    # Exclude items already covered by trigger steps
    read_comps = [c for c in read_comps if not any(s.target_name == c.source_name for s in steps)]
    comp_optional = len(read_comps) > 1
    for comp in read_comps:
        steps.append(
            step(
                "read",
                f"Read {comp.source_name}.",
                target_name=comp.source_name,
                target_type="item",
                target_key=comp.source_stable_key,
                or_group="read_completion" if comp_optional else None,
            )
        )
    return steps


def _steps_hybrid(
    step: Callable[..., QuestStep],
    giver: AcquisitionSource | None,
    completion: list[CompletionSource],
    required_items: list[RequiredItemInfo],
    zone_context: str | None,
    shout_keywords: dict[str, str],
) -> list[QuestStep]:
    """Generate steps for quests with multiple completion methods.

    Each completion source is an independent game trigger — any one of
    them completes the quest. Steps are marked as alternatives via
    ``or_group="complete"`` so the UI shows "-- OR --" separators.
    """
    steps = _emit_giver_step(step, giver)
    steps.extend(_emit_collect_steps(step, required_items))

    or_group = "complete" if len(completion) > 1 else None
    for comp in completion:
        s = _emit_completion_step(
            step,
            comp,
            shout_keywords,
            giver=giver,
            zone_context=zone_context,
            or_group=or_group,
        )
        if s:
            steps.append(s)
    return steps
