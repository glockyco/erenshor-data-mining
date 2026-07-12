"""Item section generator for wiki content.

This module generates MediaWiki template wikitext for individual items including
weapons, armor, consumables, and other item types.

This section generator produces templates for single items. Multi-entity page
assembly is handled by PageGenerator classes.

Template structure:
- All items: {{Item}} template + {{ItemTooltip|stablekey=...}}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import safe_str
from erenshor.application.wiki.generators.item_type_display import build_item_types
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase
from erenshor.domain.entities.item_kind import ItemKind, classify_item_kind
from erenshor.domain.value_objects.wiki_link import AbilityLink

if TYPE_CHECKING:
    from erenshor.domain.enriched_data.item import EnrichedItemData
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats


class ItemSectionGenerator(SectionGeneratorBase):
    """Generator for item wiki sections.

    Generates template wikitext for a SINGLE item entity. All name/page resolution
    uses direct entity attribute access and pre-built WikiLink objects from
    SourceInfo — no resolver.

    Multi-entity page assembly is handled by PageGenerator classes, not here.
    """

    def __init__(self) -> None:
        super().__init__()

    def generate_template(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate template wikitext for a single item."""
        item = enriched.item
        logger.debug(f"Generating template for item: {item.item_name} (kind: {self._classify(item)})")

        kind = self._classify(item)
        if kind == ItemKind.WEAPON and not enriched.stats:
            raise ValueError(
                f"Weapon '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )
        if kind == ItemKind.ARMOR and not enriched.stats:
            raise ValueError(
                f"Armor '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )

        template_wikitext = self._generate_tooltip_page(enriched)
        return self.normalize_wikitext(template_wikitext)

    def _classify(self, item: Item) -> ItemKind:
        return classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell_stable_key,
            teach_skill=item.teach_skill_stable_key,
            template_flag=item.template,
            click_effect=item.item_effect_on_click_stable_key,
            disposable=bool(item.disposable),
        )

    def _generate_tooltip_page(self, enriched: EnrichedItemData) -> str:
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)
        kind = self._classify(enriched.item)
        if kind in {ItemKind.WEAPON, ItemKind.ARMOR}:
            tooltip_context = self._build_parameterized_tooltip_context(enriched, kind)
            tooltip_template = self.render_template("item_tooltip.jinja2", tooltip_context)
        else:
            # Non-equipment tooltips still use the stable-key data path until
            # their legacy templates are migrated.  Equipment is self-contained:
            # only its Normal row crosses the page/module boundary.
            tooltip_template = f"{{{{ItemTooltip|stablekey={enriched.item.stable_key}}}}}"
        return f"{item_template}\n\n{tooltip_template}"

    def _build_parameterized_tooltip_context(self, enriched: EnrichedItemData, kind: ItemKind) -> dict[str, str]:
        """Build the Normal/base parameter contract consumed by ItemTooltip."""
        item = enriched.item
        stats = self._normal_stats(enriched)
        classes = {class_name.lower(): "True" for class_name in enriched.classes}
        # The old template spells the current Windblade class "Duelist".
        if "windblade" in classes:
            classes["duelist"] = "True"

        context: dict[str, str] = {
            "kind": "Weapon" if kind == ItemKind.WEAPON else "Armor",
            "image": safe_str(item.image_name or item.item_icon_name),
            "name": safe_str(item.display_name or item.item_name),
            "slot": safe_str(item.required_slot),
            "type": self._legacy_weapon_type(item) if kind == ItemKind.WEAPON else "",
            "relic": "True" if item.relic else "",
            "damage": safe_str(stats.weapon_dmg),
            "delay": safe_str(item.weapon_dly),
            "range": safe_str(item.wand_range or item.bow_range),
            "str": safe_str(stats.str_),
            "end": safe_str(stats.end_),
            "dex": safe_str(stats.dex),
            "agi": safe_str(stats.agi),
            "int": safe_str(stats.int_),
            "wis": safe_str(stats.wis),
            "cha": safe_str(stats.cha),
            "res": safe_str(stats.res),
            "health": safe_str(stats.hp),
            "mana": safe_str(stats.mana),
            "armor": safe_str(stats.ac),
            "magic": safe_str(stats.mr),
            "poison": safe_str(stats.pr),
            "elemental": safe_str(stats.er),
            "void": safe_str(stats.vr),
            "description": safe_str(item.lore),
        }
        for class_name in ("arcanist", "duelist", "druid", "paladin", "reaver", "stormcaller"):
            context[class_name] = classes.get(class_name, "")
        context.update(self._build_proc_tooltip_context(enriched))
        return context

    def _normal_stats(self, enriched: EnrichedItemData) -> ItemStats:
        for stats in enriched.stats:
            if stats.quality in {"Normal", "0"}:
                return stats
        # The exporter normally always emits Normal.  Falling back to the first
        # row keeps the existing fail-fast weapon/armor invariant while allowing
        # old databases that used quality "0" to render during migration.
        return enriched.stats[0]

    def _legacy_weapon_type(self, item: Item) -> str:
        slot = item.required_slot or ""
        if slot == "PrimaryOrSecondary":
            slot = "Primary or Secondary"
        if item.this_weapon_type in {"TwoHandMelee", "TwoHandStaff"}:
            slot += " - 2-Handed"
        return slot

    def _build_proc_tooltip_context(self, enriched: EnrichedItemData) -> dict[str, str]:
        proc = enriched.proc
        if proc is None:
            return {}
        spell = proc.spell
        if spell is None:
            return {"proc_style": safe_str(proc.proc_style), "proc_chance": safe_str(proc.proc_chance)}
        return {
            "proc_style": safe_str(proc.proc_style),
            "proc_chance": safe_str(proc.proc_chance),
            "proc_spell_icon": safe_str(spell.image_name or spell.spell_icon_name),
            "proc_spell_name": safe_str(spell.display_name or spell.spell_name),
            "proc_spell_level": safe_str(spell.required_level),
            "proc_spell_duration_ticks": safe_str(spell.spell_duration_in_ticks),
            "proc_spell_type": safe_str(spell.type),
            "proc_spell_line": safe_str(spell.line),
            "proc_target_damage": safe_str(spell.target_damage),
            "proc_target_healing": safe_str(spell.target_healing),
            "proc_shielding_amt": safe_str(spell.shielding_amt),
            "proc_damage_type": safe_str(spell.damage_type),
            "proc_cast_time": safe_str(spell.spell_charge_time),
            "proc_cooldown": safe_str(spell.cooldown),
            "proc_spell_range": safe_str(spell.spell_range),
            "proc_lifetap": safe_str(spell.lifetap),
            "proc_group_effect": safe_str(spell.group_effect),
            "proc_stun_target": safe_str(spell.stun_target),
            "proc_charm_target": safe_str(spell.charm_target),
            "proc_root_target": safe_str(spell.root_target),
            "proc_taunt_spell": safe_str(spell.taunt_spell),
            "proc_aggro": safe_str(spell.aggro),
            "proc_status_effect_name": safe_str(spell.status_effect_to_apply_stable_key),
            "proc_hp": safe_str(spell.hp),
            "proc_ac": safe_str(spell.ac),
            "proc_mana": safe_str(spell.mana),
            "proc_str": safe_str(spell.str_),
            "proc_dex": safe_str(spell.dex),
            "proc_end": safe_str(spell.end_),
            "proc_agi": safe_str(spell.agi),
            "proc_wis": safe_str(spell.wis),
            "proc_int": safe_str(spell.int_),
            "proc_cha": safe_str(spell.cha),
            "proc_mr": safe_str(spell.mr),
            "proc_er": safe_str(spell.er),
            "proc_pr": safe_str(spell.pr),
            "proc_vr": safe_str(spell.vr),
            "proc_movement_speed": safe_str(spell.movement_speed),
            "proc_damage_shield": safe_str(spell.damage_shield),
            "proc_haste": safe_str(spell.haste),
            "proc_percent_lifesteal": safe_str(spell.percent_lifesteal),
            "proc_atk_roll_modifier": safe_str(spell.atk_roll_modifier),
            "proc_resonate_chance": safe_str(spell.resonate_chance),
            "proc_add_proc_name": safe_str(spell.add_proc_stable_key),
            "proc_add_proc_chance": safe_str(spell.add_proc_chance),
            "proc_special_descriptor": safe_str(spell.special_descriptor),
            "proc_xp_bonus": safe_str(spell.xp_bonus),
        }

    def _build_item_infobox_context(self, enriched: EnrichedItemData) -> dict[str, str]:
        """Build context for {{Item}} infobox template."""
        item = enriched.item
        kind = self._classify(item)

        quest_requirement_links = enriched.sources.quest_requirements if enriched.sources else []
        component_for_links = enriched.sources.component_for if enriched.sources else []

        # build_item_types needs string lists; pass display names
        quest_req_strs = [link.display_name for link in quest_requirement_links]
        component_for_strs = [link.display_name for link in component_for_links]

        item_type = build_item_types(
            item=item,
            item_kind=kind,
            quest_requirements=quest_req_strs,
            component_for=component_for_strs,
        )

        display_name = item.display_name or item.item_name or ""

        vendor_sources = self._format_vendor_sources(enriched)
        drop_sources = self._format_drop_sources(enriched)
        quest_rewards_str, quest_requirements_str = self._format_quest_sources(enriched)
        craft_sources, component_for_str = self._format_crafting_sources(enriched)

        # Taught spell link — use AbilityLink-style wikitext directly
        taughtspell = ""
        if item.teach_spell_stable_key and enriched.taught_spell:
            sp = enriched.taught_spell
            taughtspell = str(
                AbilityLink(
                    page_title=sp.wiki_page_name,
                    display_name=sp.display_name or sp.spell_name or "",
                    image_name=sp.image_name,
                )
            )

        # Taught skill link
        taughtskill = ""
        if item.teach_skill_stable_key and enriched.taught_skill:
            sk = enriched.taught_skill
            taughtskill = str(
                AbilityLink(
                    page_title=sk.wiki_page_name,
                    display_name=sk.display_name or sk.skill_name or "",
                    image_name=sk.image_name,
                )
            )

        return {
            "title": display_name,
            "type": item_type,
            "vendorsource": vendor_sources,
            "source": drop_sources,
            "othersource": "",
            "questsource": quest_rewards_str,
            "relatedquest": quest_requirements_str,
            "craftsource": craft_sources,
            "componentfor": component_for_str,
            "buy": safe_str(item.item_value) if item.item_value else "",
            "sell": safe_str(item.sell_value) if item.sell_value else "",
            "taughtspell": taughtspell,
            "taughtskill": taughtskill,
        }

    def _format_vendor_sources(self, enriched: EnrichedItemData) -> str:
        """Format vendor sources from pre-built CharacterLink objects."""
        if not enriched.sources or not enriched.sources.vendors:
            return ""
        visible = [link for link in enriched.sources.vendors if link.page_title is not None]
        visible.sort()
        seen: set[str] = set()
        result = []
        for link in visible:
            s = str(link)
            if s not in seen:
                seen.add(s)
                result.append(s)
        return "<br>".join(result)

    def _format_drop_sources(self, enriched: EnrichedItemData) -> str:
        """Format drop sources from pre-built WikiLink objects with probabilities."""
        if not enriched.sources or not enriched.sources.drops:
            return ""
        drop_data = [(link, prob) for link, prob in enriched.sources.drops if link.page_title is not None]
        drop_data.sort(key=lambda x: (-x[1], x[0]))
        seen: set[tuple[str, float]] = set()
        result = []
        for link, probability in drop_data:
            key = (str(link), probability)
            if key not in seen:
                seen.add(key)
                result.append(f"{link!s} ({probability:.1f}%)")
        return "<br>".join(result)

    def _format_quest_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        """Format quest reward and requirement sources from pre-built QuestLink objects."""
        if not enriched.sources:
            return ("", "")

        reward_links = [link for link in enriched.sources.quest_rewards if link.page_title is not None]
        reward_links.sort()
        seen_r: set[str] = set()
        rewards_result = []
        for link in reward_links:
            s = str(link)
            if s not in seen_r:
                seen_r.add(s)
                rewards_result.append(s)

        req_links = [link for link in enriched.sources.quest_requirements if link.page_title is not None]
        req_links.sort()
        seen_q: set[str] = set()
        reqs_result = []
        for link in req_links:
            s = str(link)
            if s not in seen_q:
                seen_q.add(s)
                reqs_result.append(s)

        return ("<br>".join(rewards_result), "<br>".join(reqs_result))

    def _format_crafting_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        """Format crafting sources from pre-built ItemLink tuples."""
        if not enriched.sources:
            return ("", "")
        craft_links = [f"{qty}x {link!s}" for link, qty in enriched.sources.craft_recipe]
        component_links = [str(link) for link in enriched.sources.component_for]
        return ("<br>".join(craft_links), "<br>".join(component_links))
