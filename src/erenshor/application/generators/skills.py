"""Skill content generator.

Generates wiki content for skills from the database, yielding one skill at a time
for streaming and progress tracking.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.ability_helpers import (
    GAME_TICKS_PER_SECOND,
    build_sorted_classes_list,
    create_ability_cache,
    parse_spell_reference,
)
from erenshor.application.generators.base import BaseGenerator, GeneratedContent
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities.page import EntityRef
from erenshor.domain.services import is_item_obtainable
from erenshor.infrastructure.database.repositories import (
    get_items_that_teach_spell,
    get_skills,
    get_spell_by_id,
)
from erenshor.infrastructure.templates.contexts.abilities import (
    SkillInfoboxContext,
)
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.core import WikiRegistry
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR
from erenshor.shared.text import normalize_wikitext, seconds_to_duration

__all__ = ["SkillGenerator"]


class SkillGenerator(BaseGenerator):
    """Generate skill page content from database.

    Extracts all skill data from database, builds template contexts, renders Jinja2
    templates, and yields GeneratedContent one skill at a time.

    Skills are abilities that don't cost mana, from the Skills table. They use the
    same template structure as spells but with different field values.
    """

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate skill content with streaming.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Optional filter string (name or 'id:skill_name') to process specific skills

        Yields:
            GeneratedContent for each skill, one at a time
        """
        link_resolver = RegistryLinkResolver(registry)

        skills = get_skills(engine)

        # Apply filter if provided
        if filter:
            skills = [
                skill
                for skill in skills
                if self._matches_filter(
                    skill.SkillName or "", skill.ResourceName, filter
                )
            ]

        # Create cache for spell lookups (for effect references)
        # Note: Effects ALWAYS reference spells, never skills (game mechanics constraint)
        get_cached_spell = create_ability_cache(engine, get_spell_by_id)

        for db_skill in skills:
            # Check if entity is in registry (skip if explicitly excluded)
            entity_ref = EntityRef.from_skill(db_skill)
            # Only skip if registry has pages (i.e., has been built)
            # Empty registry means first run or test - don't skip
            if registry.pages and not registry.resolve_entity(entity_ref):
                # Entity excluded from registry - skip generation
                continue

            page_title = link_resolver.resolve_spell_title(
                db_skill.ResourceName, db_skill.SkillName
            )

            # Get items that teach this skill (skill books) - needed for source and classes logic
            teach_items = get_items_that_teach_spell(engine, db_skill.Id)

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

            # Build classes list with required levels for skills
            # Only populate classes if there's an obtainable teaching item
            has_obtainable_teaching_item = bool(obtainable_teach_items)

            class_levels = [
                ("Duelist", db_skill.DuelistRequiredLevel),
                ("Paladin", db_skill.PaladinRequiredLevel),
                ("Arcanist", db_skill.ArcanistRequiredLevel),
                ("Druid", db_skill.DruidRequiredLevel),
                ("Stormcaller", db_skill.StormcallerRequiredLevel),
            ]
            # Filter to only include classes when an obtainable teaching item exists
            skill_classes_list = (
                build_sorted_classes_list(class_levels)
                if has_obtainable_teaching_item
                else []
            )

            # Skills use the same template structure as spells
            skill_type = db_skill.TypeOfSkill or "Passive"

            # Determine casttime: non-innate skills are instant
            casttime = ""
            if db_skill.TypeOfSkill and db_skill.TypeOfSkill != "Innate":
                casttime = "Instant"

            # Build cooldown string
            # Skills.Cooldown is in game ticks, convert to seconds
            cooldown_str = seconds_to_duration(
                (db_skill.Cooldown / GAME_TICKS_PER_SECOND) if db_skill.Cooldown else 0
            )

            # Build effects from EffectToApplyId and CastOnTargetId
            # Both reference spells only (game mechanics constraint)
            effects_parts: list[str] = []
            seen_effects: set[str] = set()

            if db_skill.EffectToApplyId:
                effect_link = parse_spell_reference(
                    db_skill.EffectToApplyId,
                    link_resolver,
                    get_cached_spell,
                )
                if effect_link not in seen_effects:
                    effects_parts.append(effect_link)
                    seen_effects.add(effect_link)

            if db_skill.CastOnTargetId:
                effect_link = parse_spell_reference(
                    db_skill.CastOnTargetId,
                    link_resolver,
                    get_cached_spell,
                )
                if effect_link not in seen_effects:
                    effects_parts.append(effect_link)
                    seen_effects.add(effect_link)

            effects_str = WIKITEXT_LINE_SEPARATOR.join(effects_parts)

            # Build description with equipment requirements
            description = db_skill.SkillDesc or ""
            if db_skill.RequireBow:
                # Only add if "require" doesn't already appear in description
                if "require" not in description.lower():
                    description = (
                        description + "<br>Requires a bow."
                        if description
                        else "Requires a bow."
                    )
            if db_skill.RequireShield:
                # Only add if "require" doesn't already appear in description
                if "require" not in description.lower():
                    description = (
                        description + "<br>Requires a shield."
                        if description
                        else "Requires a shield."
                    )

            damage_type = db_skill.DamageType if skill_type == "Attack" else ""

            display_name = registry.get_display_name(entity_ref)
            image_name = registry.get_image_name(entity_ref)
            context = SkillInfoboxContext(
                block_id=db_skill.ResourceName,
                id=db_skill.Id,
                title=display_name,
                image=f"{image_name}.png",
                imagecaption="",
                description=description,
                type=skill_type,
                classes=skill_classes_list,
                casttime=casttime,
                cooldown=cooldown_str,
                effects=effects_str,
                damage_type=damage_type,
                source=source_str,
            )

            # Render skill infobox
            rendered = normalize_wikitext(
                render_template("abilities/ability.j2", context)
            )
            blocks = [
                RenderedBlock(
                    page_title=page_title,
                    block_id=db_skill.ResourceName,
                    template_key="Infobox_ability",
                    text=rendered,
                )
            ]

            entity_ref = EntityRef.from_skill(db_skill)

            yield GeneratedContent(
                entity_ref=entity_ref,
                page_title=page_title,
                rendered_blocks=blocks,
            )
