"""Spell content generator.

Generates wiki content for spells from the database, yielding one spell at a time
for streaming and progress tracking.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.ability_helpers import (
    build_sorted_classes_list,
    create_ability_cache,
    parse_spell_reference,
)
from erenshor.application.generators.base import BaseGenerator, GeneratedContent
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities import db_spell_to_domain
from erenshor.domain.entities.page import EntityRef
from erenshor.domain.services import is_item_obtainable
from erenshor.infrastructure.database.repositories import (
    get_character_by_object_name,
    get_items_that_teach_spell,
    get_items_with_effects_for_spell,
    get_spell_by_id,
    get_spells,
)
from erenshor.infrastructure.templates.contexts.abilities import (
    SpellInfoboxContext,
)
from erenshor.registry.core import WikiRegistry
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import (
    GAME_TICKS_PER_SECOND,
    INSTANT_CAST_THRESHOLD,
    SECONDS_PER_DURATION_TICK,
    WIKITEXT_LINE_SEPARATOR,
)
from erenshor.shared.text import (
    normalize_wikitext,
    seconds_to_duration,
    to_string_or_blank,
)

__all__ = ["SpellGenerator"]


class SpellGenerator(BaseGenerator):
    """Generate spell page content from database.

    Extracts all spell data from database, builds template contexts, renders Jinja2
    templates, and yields GeneratedContent one spell at a time.

    Spells are combat abilities from the Spells table with full combat mechanics
    including damage, healing, buffs, debuffs, and crowd control.
    """

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate spell content with streaming.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Optional filter string (name or 'id:spell_name') to process specific spells

        Yields:
            GeneratedContent for each spell, one at a time
        """
        link_resolver = RegistryLinkResolver(registry)

        spells = get_spells(engine, obtainable_only=True)

        # Apply filter if provided
        if filter:
            spells = [
                spell
                for spell in spells
                if self._matches_filter(
                    spell.SpellName or "", spell.ResourceName, filter
                )
            ]

        # Create cache for spell lookups (for AddProc references)
        # Note: Effects and procs ALWAYS reference spells, never skills
        get_cached_spell = create_ability_cache(engine, get_spell_by_id)

        for db_spell in spells:
            spell = db_spell_to_domain(db_spell)

            # Check if entity is in registry (skip if explicitly excluded)
            entity_ref = EntityRef.from_spell(db_spell)
            # Only skip if registry has pages (i.e., has been built)
            # Empty registry means first run or test - don't skip
            if registry.pages and not registry.resolve_entity(entity_ref):
                # Entity excluded from registry - skip generation
                continue

            page_title = link_resolver.resolve_spell_title(
                spell.resource_name, spell.name
            )

            # Get items that teach this spell (needed for source and classes logic)
            teach_items = get_items_that_teach_spell(engine, db_spell.Id)

            # Filter to only obtainable teaching items
            # Both source and classes fields should only show obtainable items
            obtainable_teach_items = [
                item
                for item in teach_items
                if is_item_obtainable(engine, item.Id, item.ItemName)
            ]

            # Build source string from obtainable teaching items only
            source_str = (
                WIKITEXT_LINE_SEPARATOR.join(
                    link_resolver.item_link(
                        getattr(i, "ResourceName", ""),
                        i.ItemName,
                        getattr(i, "Id", None),
                    )
                    for i in obtainable_teach_items
                )
                if obtainable_teach_items
                else ""
            )

            # Build classes list with required levels
            # Only populate classes if there's an obtainable teaching item
            has_obtainable_teaching_item = bool(obtainable_teach_items)

            class_level_pairs: list[tuple[str, int | None]] = []
            if has_obtainable_teaching_item and db_spell.Classes:
                for cname in db_spell.Classes:
                    class_level_pairs.append((cname, db_spell.RequiredLevel))
            classes_list = build_sorted_classes_list(class_level_pairs)

            # Build imagecaption from StatusEffectMessageOnPlayer
            imagecaption = (
                ""
                if not db_spell.StatusEffectMessageOnPlayer
                else f"You {db_spell.StatusEffectMessageOnPlayer}"
            )

            # Build cast time string
            # SpellChargeTime is in game ticks (GAME_TICKS_PER_SECOND ticks per second)
            cast_time_str = ""
            if db_spell.SpellChargeTime:
                secs = db_spell.SpellChargeTime / GAME_TICKS_PER_SECOND
                # If rounds to 0.0, treat as instant
                if secs < INSTANT_CAST_THRESHOLD:
                    cast_time_str = "Instant"
                else:
                    cast_time_str = f"{secs:.1f} seconds"
            else:
                # No cast time means instant cast
                cast_time_str = "Instant"

            # Get items with this spell effect
            eff_items = get_items_with_effects_for_spell(engine, db_spell.Id)
            itemswitheffect_str = (
                WIKITEXT_LINE_SEPARATOR.join(
                    link_resolver.item_link(
                        getattr(i, "ResourceName", ""),
                        i.ItemName,
                        getattr(i, "Id", None),
                    )
                    for i in eff_items
                )
                if eff_items
                else ""
            )

            # Parse AddProc field for linked spells
            add_proc = ""
            if db_spell.AddProc:
                add_proc = parse_spell_reference(
                    db_spell.AddProc,
                    link_resolver,
                    get_cached_spell,
                )

            # Resolve character link if this spell summons a pet
            pet_to_summon = ""
            if db_spell.PetToSummonResourceName:
                summoned_char = get_character_by_object_name(
                    engine, db_spell.PetToSummonResourceName
                )
                if summoned_char:
                    char_ref = EntityRef.from_character(summoned_char)
                    pet_to_summon = link_resolver.character_link(char_ref)
                else:
                    # Fallback to plain text if character not found
                    pet_to_summon = db_spell.PetToSummonResourceName

            # Build spell infobox context
            display_name = registry.get_display_name(entity_ref)
            image_name = registry.get_image_name(entity_ref)
            context = SpellInfoboxContext(
                block_id=spell.resource_name,
                id=spell.id,
                title=display_name,
                image=f"{image_name}.png",
                imagecaption=imagecaption,
                description=spell.description or "",
                type=spell.type or "",
                line=spell.line or "",
                classes=classes_list,
                required_level=to_string_or_blank(
                    db_spell.RequiredLevel, zero_as_blank=True
                ),
                manacost=to_string_or_blank(db_spell.ManaCost, zero_as_blank=True),
                aggro=to_string_or_blank(
                    db_spell.__dict__.get("Aggro", None), zero_as_blank=True
                ),
                is_taunt=bool(getattr(db_spell, "TauntSpell", False)),
                casttime=cast_time_str,
                # Spells.Cooldown is already in seconds (unlike Skills.Cooldown which is in ticks)
                cooldown=seconds_to_duration(
                    db_spell.Cooldown if db_spell.Cooldown else 0
                ),
                # Spells.SpellDurationInTicks stored in 6-second intervals
                duration=(
                    seconds_to_duration(
                        db_spell.SpellDurationInTicks * SECONDS_PER_DURATION_TICK
                    )
                    if db_spell.SpellDurationInTicks
                    else ""
                ),
                duration_in_ticks=(
                    ""
                    if not db_spell.SpellDurationInTicks
                    else f"{db_spell.SpellDurationInTicks} ticks"
                ),
                has_unstable_duration=bool(
                    getattr(db_spell, "UnstableDuration", False)
                ),
                is_instant_effect=bool(db_spell.InstantEffect),
                is_reap_and_renew=bool(getattr(db_spell, "ReapAndRenew", False)),
                is_sim_usable=bool(getattr(db_spell, "SimUsable", True)),
                range=(
                    ""
                    if db_spell.SelfOnly or not db_spell.SpellRange
                    else to_string_or_blank(db_spell.SpellRange, zero_as_blank=True)
                ),
                max_level_target=to_string_or_blank(
                    db_spell.MaxLevelTarget, zero_as_blank=True
                ),
                is_self_only=bool(db_spell.SelfOnly),
                is_group_effect=bool(db_spell.GroupEffect),
                is_applied_to_caster=bool(db_spell.ApplyToCaster),
                effects="",  # Spells don't use effects field (skills do)
                damage_type=(
                    (db_spell.DamageType or "") if db_spell.TargetDamage else ""
                ),
                resist_modifier=to_string_or_blank(
                    db_spell.ResistModifier, zero_as_blank=True
                ),
                target_damage=to_string_or_blank(
                    db_spell.TargetDamage, zero_as_blank=True
                ),
                target_healing=to_string_or_blank(
                    getattr(db_spell, "TargetHealing", 0), zero_as_blank=True
                ),
                caster_healing=to_string_or_blank(
                    getattr(db_spell, "CasterHealing", 0), zero_as_blank=True
                ),
                shield_amount=to_string_or_blank(
                    db_spell.ShieldingAmt, zero_as_blank=True
                ),
                pet_to_summon=pet_to_summon,
                status_effect=(
                    (lambda n: f"[[{n}]]")(
                        db_spell.StatusEffectToApply.split("(")[0].strip()
                    )
                    if db_spell.StatusEffectToApply
                    else ""
                ),
                add_proc=add_proc,
                add_proc_chance=to_string_or_blank(
                    db_spell.AddProcChance, zero_as_blank=True
                ),
                has_lifetap=bool(getattr(db_spell, "Lifetap", False)),
                lifesteal=(
                    f"{db_spell.PercentLifesteal}%" if db_spell.PercentLifesteal else ""
                ),
                damage_shield=to_string_or_blank(
                    db_spell.__dict__.get("DamageShield", None), zero_as_blank=True
                ),
                percent_mana_restoration=(
                    f"{db_spell.PercentManaRestoration}%"
                    if db_spell.PercentManaRestoration
                    else ""
                ),
                bleed_damage_percent=(
                    f"{db_spell.BleedDamagePercent}%"
                    if db_spell.BleedDamagePercent
                    else ""
                ),
                special_descriptor=db_spell.SpecialDescriptor or "",
                hp=to_string_or_blank(db_spell.HP, zero_as_blank=True),
                ac=to_string_or_blank(db_spell.AC, zero_as_blank=True),
                mana=to_string_or_blank(db_spell.Mana, zero_as_blank=True),
                str=to_string_or_blank(db_spell.Str, zero_as_blank=True),
                dex=to_string_or_blank(db_spell.Dex, zero_as_blank=True),
                end=to_string_or_blank(db_spell.End, zero_as_blank=True),
                agi=to_string_or_blank(db_spell.Agi, zero_as_blank=True),
                wis=to_string_or_blank(db_spell.Wis, zero_as_blank=True),
                int=to_string_or_blank(db_spell.Int, zero_as_blank=True),
                cha=to_string_or_blank(db_spell.Cha, zero_as_blank=True),
                mr=to_string_or_blank(db_spell.MR, zero_as_blank=True),
                er=to_string_or_blank(db_spell.ER, zero_as_blank=True),
                vr=to_string_or_blank(db_spell.VR, zero_as_blank=True),
                pr=to_string_or_blank(db_spell.PR, zero_as_blank=True),
                haste=(f"{db_spell.Haste}%" if db_spell.Haste else ""),
                resonance=to_string_or_blank(
                    db_spell.__dict__.get("ResonateChance", None), zero_as_blank=True
                ),
                movement_speed=to_string_or_blank(
                    db_spell.MovementSpeed, zero_as_blank=True
                ),
                atk_roll_modifier=to_string_or_blank(
                    db_spell.AtkRollModifier, zero_as_blank=True
                ),
                # Only show xp_bonus if spell has duration (XP bonus is meaningless without duration)
                xp_bonus=(
                    f"{db_spell.XPBonus * 100:.1f}%"
                    if db_spell.XPBonus and db_spell.SpellDurationInTicks
                    else ""
                ),
                is_root=bool(getattr(db_spell, "RootTarget", False)),
                is_stun=bool(getattr(db_spell, "StunTarget", False)),
                is_charm=bool(getattr(db_spell, "CharmTarget", False)),
                is_broken_on_damage=bool(getattr(db_spell, "BreakOnDamage", False)),
                itemswitheffect=itemswitheffect_str,
                source=source_str,
            )

            # Render spell infobox
            rendered = normalize_wikitext(
                self._renderer.render("abilities/ability.j2", ctx=context)
            )
            blocks = [
                RenderedBlock(
                    page_title=page_title,
                    block_id=spell.resource_name,
                    template_key="Infobox_ability",
                    text=rendered,
                )
            ]

            entity_ref = EntityRef.from_spell(db_spell)

            yield GeneratedContent(
                entity_ref=entity_ref,
                page_title=page_title,
                rendered_blocks=blocks,
            )
