"""Item section generator for wiki content.

This module generates MediaWiki template wikitext for individual items including
weapons, armor, consumables, and other item types.

This section generator produces templates for single items. Multi-entity page
assembly is handled by PageGenerator classes.

Template structure:
- Equipment (weapons, armor): {{Item}} infobox + one parameterized {{ItemTooltip}}
  carrying the Standard-quality stats; quality variants derive inside Lua.
- All other kinds: {{Item}} infobox + their legacy template ({{Item/General}},
  {{Item/Aura}}, ...), which the live gadget CSS already styles.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import format_description, safe_str
from erenshor.application.wiki.generators.item_type_display import build_item_types
from erenshor.application.wiki.generators.link_lists import fold_long_list
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase
from erenshor.domain.entities.item_kind import ItemKind, classify_item_kind
from erenshor.domain.value_objects.item_provenance import (
    PROVENANCE_SCHEMA_VERSION,
    ItemAcquisition,
    ProvenanceCondition,
    fact_to_dict,
    is_actionable_acquisition,
)
from erenshor.domain.value_objects.wiki_filename import picture_file_title
from erenshor.domain.value_objects.wiki_link import AbilityLink
from erenshor.shared.game_constants import LONG_NAME_FONT_SIZE, LONG_NAME_THRESHOLD, WIKITEXT_LINE_SEPARATOR

if TYPE_CHECKING:
    from erenshor.domain.enriched_data.item import EnrichedItemData
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.domain.entities.spell import Spell
    from erenshor.domain.value_objects.source_info import SourceInfo

# Parameter names understood by the legacy Item/* class-restriction rows.  The
# game renamed Duelist to Windblade; the live templates still spell the
# parameter "duelist".
_LEGACY_CLASS_PARAMS = ("arcanist", "duelist", "druid", "paladin", "reaver", "stormcaller")


def item_image_file(item: Item) -> str:
    """The file title of an item's icon, which its tooltip template shows."""
    return picture_file_title("icon", item.image_name, item.display_name, item.item_name)


class ItemSectionGenerator(SectionGeneratorBase):
    """Render one item from canonical facts and resolved presentation links.

    Multi-entity page assembly is handled by PageGenerator classes.
    """

    def __init__(self) -> None:
        super().__init__()

    def generate_template(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate template wikitext for a single item."""
        item = enriched.item
        kind = self._classify(item)
        logger.debug(f"Generating template for item: {item.item_name} (kind: {kind})")

        if kind in (ItemKind.WEAPON, ItemKind.ARMOR):
            template_wikitext = self._generate_equipment_page(enriched, kind)
        elif kind == ItemKind.CHARM:
            template_wikitext = self._generate_charm_page(enriched)
        elif kind == ItemKind.AURA:
            template_wikitext = self._generate_aura_page(enriched)
        elif kind == ItemKind.SPELL_SCROLL:
            template_wikitext = self._generate_spellscroll_page(enriched)
        elif kind == ItemKind.SKILL_BOOK:
            template_wikitext = self._generate_skillbook_page(enriched)
        elif kind == ItemKind.CONSUMABLE:
            template_wikitext = self._generate_consumable_page(enriched)
        elif kind == ItemKind.MOLD:
            template_wikitext = self._generate_mold_page(enriched)
        else:
            template_wikitext = self._generate_general_page(enriched)

        return self.normalize_wikitext(template_wikitext)

    def _classify(self, item: Item) -> ItemKind:
        return classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell_stable_key,
            teach_skill=item.teach_skill_stable_key,
            template_flag=item.template,
            click_effect=item.item_effect_on_click_stable_key,
            disposable=bool(item.disposable),
            cosmetic=item.cosmetic_effect is not None,
        )

    # ------------------------------------------------------------------
    # Equipment (parameterized quality tooltip)
    # ------------------------------------------------------------------

    def _generate_equipment_page(self, enriched: EnrichedItemData, kind: ItemKind) -> str:
        if not enriched.stats:
            item = enriched.item
            raise ValueError(
                f"{kind.capitalize()} '{item.item_name}' ({item.stable_key}) has no ItemStats"
                " - this should NEVER happen!"
            )
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)
        tooltip_context = self._build_parameterized_tooltip_context(enriched, kind)
        tooltip_template = self.render_template("item_tooltip.jinja2", tooltip_context)
        return f"{item_template}\n\n{tooltip_template}"

    def _build_parameterized_tooltip_context(self, enriched: EnrichedItemData, kind: ItemKind) -> dict[str, str]:
        """Build the Standard/base parameter contract consumed by ItemTooltip.

        Values are display-ready: they match what the legacy generator wrote
        into explicit Item/Weapon and Item/Armor invocations, so the Lua
        renderer can forward them to those templates untouched.
        """
        item = enriched.item
        stats = self._normal_stats(enriched)
        display_name = item.display_name or item.item_name or ""

        context: dict[str, str] = {
            "kind": "Weapon" if kind == ItemKind.WEAPON else "Armor",
            "icon": item_image_file(item),
            "name": self._format_long_item_name(display_name),
            "slot": safe_str(item.required_slot),
            "type": self._weapon_type_display(item.required_slot, item.this_weapon_type)
            if kind == ItemKind.WEAPON
            else "",
            "two_handed": "True"
            if kind == ItemKind.WEAPON and item.this_weapon_type in ("TwoHandMelee", "TwoHandStaff", "TwoHandBow")
            else "",
            "relic": "True" if item.relic else "",
            "must_equip": "True" if item.must_be_equipped_to_click and item.item_effect_on_click_stable_key else "",
            "value": self._item_window_value(item),
            "damage": safe_str(stats.weapon_dmg) if stats.weapon_dmg else "",
            "delay": safe_str(item.weapon_dly) if item.weapon_dly else "",
            "range": self._get_weapon_range(item, stats.weapon_dmg),
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
            "description": format_description(safe_str(item.lore)) if item.lore else "",
        }
        context.update(self._legacy_class_flags(enriched.classes))
        context.update(self._build_proc_tooltip_context(enriched))
        return context

    def _item_window_value(self, item: Item) -> str:
        if item.item_value is not None and item.item_value > 0 and not item.no_trade_no_destroy:
            return safe_str(item.item_value)
        return "Unsellable"

    def _normal_stats(self, enriched: EnrichedItemData) -> ItemStats:
        for stats in enriched.stats:
            if stats.quality == "Standard":
                return stats
        # The exporter always emits Standard for equipment.  Falling back to
        # the first row keeps the fail-fast weapon/armor invariant for records
        # that arrive in an unexpected order.
        return enriched.stats[0]

    def _format_long_item_name(self, display_name: str) -> str:
        if len(display_name) > LONG_NAME_THRESHOLD:
            return f'<span style="font-size:{LONG_NAME_FONT_SIZE}">{display_name}</span>'
        return display_name

    def _weapon_type_display(self, required_slot: str | None, this_weapon_type: str | None) -> str:
        slot = (required_slot if required_slot is not None else "").strip()
        if slot == "PrimaryOrSecondary":
            slot = "Primary or Secondary"
        weapon_kind = (this_weapon_type if this_weapon_type is not None else "").strip()
        two_handed = weapon_kind in ("TwoHandMelee", "TwoHandStaff")
        if two_handed:
            slot += " - 2-Handed"
        return slot

    def _get_weapon_range(self, item: Item, damage: int | None) -> str:
        if not (damage or item.weapon_dly):
            return ""
        if item.is_wand:
            return safe_str(item.wand_range or 0)
        if item.is_bow:
            return safe_str(item.bow_range or 0)
        return "1"

    def _legacy_class_flags(self, class_names: list[str]) -> dict[str, str]:
        flagged = {name.lower() for name in class_names}
        if "windblade" in flagged:
            flagged.add("duelist")
        return {name: "True" if name in flagged else "" for name in _LEGACY_CLASS_PARAMS}

    def _build_proc_tooltip_context(self, enriched: EnrichedItemData) -> dict[str, str]:
        proc = enriched.proc
        spell = proc.spell if proc else None
        context = self._build_spell_details_context(spell, prefix="proc")
        context["proc_style"] = safe_str(proc.proc_style) if proc else ""
        context["proc_chance"] = safe_str(proc.proc_chance) if proc else ""
        return context

    # ------------------------------------------------------------------
    # Non-equipment kinds (legacy templates)
    # ------------------------------------------------------------------

    def _generate_charm_page(self, enriched: EnrichedItemData) -> str:
        stats = enriched.stats
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)
        if stats:
            charm_context = self._build_charm_context(enriched, stats[0])
            charm_template = self.render_template("charm.jinja2", charm_context)
            return f"{item_template}\n\n{charm_template}"
        return item_template

    def _build_charm_context(self, enriched: EnrichedItemData, stat: ItemStats) -> dict[str, str]:
        item = enriched.item

        def format_scaling(value: float | None) -> str:
            if value is None or value == 0.0:
                return ""
            return str(round(value))

        display_name = item.display_name or item.item_name or ""
        return {
            "icon": item_image_file(item),
            "name": display_name,
            "value": self._item_window_value(item),
            "tier": "0",
            "strscaling": format_scaling(stat.str_scaling),
            "endscaling": format_scaling(stat.end_scaling),
            "dexscaling": format_scaling(stat.dex_scaling),
            "agiscaling": format_scaling(stat.agi_scaling),
            "intscaling": format_scaling(stat.int_scaling),
            "wisscaling": format_scaling(stat.wis_scaling),
            "chascaling": format_scaling(stat.cha_scaling),
            "resistscaling": format_scaling(stat.resist_scaling),
            "mitigationscaling": format_scaling(stat.mitigation_scaling),
            **self._legacy_class_flags(enriched.classes),
        }

    def _generate_aura_page(self, enriched: EnrichedItemData) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        spell_details = self._build_spell_details_context(enriched.aura_spell, prefix="aura")

        aura_context = {
            "icon": item_image_file(item),
            "name": display_name,
            "value": self._item_window_value(item),
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            **spell_details,
        }

        aura_template = self.render_template("aura.jinja2", aura_context)
        return f"{item_template}\n\n{aura_template}"

    def _generate_spellscroll_page(self, enriched: EnrichedItemData) -> str:
        item = enriched.item
        spell = enriched.taught_spell

        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        # Reading a scroll is gated on the scroll's own class restrictions, not on
        # the taught spell's UsedBy list (which only drives SimPlayer behaviour).
        scroll_classes = enriched.classes
        required_level = str(spell.required_level) if spell and spell.required_level else ""

        def class_level(class_name: str) -> str:
            return required_level if class_name in scroll_classes else ""

        spellscroll_context = {
            "icon": item_image_file(item),
            "name": display_name,
            "value": self._item_window_value(item),
            "arcanist_level": class_level("Arcanist"),
            "druid_level": class_level("Druid"),
            "duelist_level": class_level("Duelist"),
            "paladin_level": class_level("Paladin"),
            "stormcaller_level": class_level("Stormcaller"),
            "reaver_level": class_level("Reaver"),
            "mana_cost": str(spell.mana_cost) if spell and spell.mana_cost else "",
            "spell_type": spell.type if spell and spell.type else "",
            "spell_desc": format_description(spell.spell_desc) if spell and spell.spell_desc else "",
        }

        spellscroll_template = self.render_template("spellscroll.jinja2", spellscroll_context)
        return f"{item_template}\n\n{spellscroll_template}"

    def _generate_skillbook_page(self, enriched: EnrichedItemData) -> str:
        item = enriched.item
        skill = enriched.taught_skill

        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""

        def level_str(val: int | None) -> str:
            if val is None or val == 0:
                return ""
            return str(val)

        skillbook_context = {
            "icon": item_image_file(item),
            "name": display_name,
            "value": self._item_window_value(item),
            "duelist_level": level_str(skill.duelist_required_level) if skill else "",
            "druid_level": level_str(skill.druid_required_level) if skill else "",
            "arcanist_level": level_str(skill.arcanist_required_level) if skill else "",
            "paladin_level": level_str(skill.paladin_required_level) if skill else "",
            "stormcaller_level": level_str(skill.stormcaller_required_level) if skill else "",
            "reaver_level": level_str(skill.reaver_required_level) if skill else "",
            "skill_type": skill.type_of_skill if skill and skill.type_of_skill else "",
            "skill_desc": format_description(skill.skill_desc) if skill and skill.skill_desc else "",
            "simplayers_autolearn": "True" if skill and skill.sim_players_autolearn else "",
        }

        skillbook_template = self.render_template("skillbook.jinja2", skillbook_context)
        return f"{item_template}\n\n{skillbook_template}"

    def _generate_consumable_page(self, enriched: EnrichedItemData) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        effect_spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(effect_spell, prefix="effect")

        consumable_context = {
            "icon": item_image_file(item),
            "name": display_name,
            "value": self._item_window_value(item),
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "disposable": "True" if item.disposable else "",
            **spell_details,
        }

        consumable_template = self.render_template("consumable.jinja2", consumable_context)
        return f"{item_template}\n\n{consumable_template}"

    def _generate_mold_page(self, enriched: EnrichedItemData) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        ingredients = ""
        rewards = ""
        if enriched.sources:
            ingredient_links = [f"{quantity}x {link!s}" for link, quantity in enriched.sources.recipe_ingredients]
            ingredients = "<br>".join(ingredient_links)

            rewards = "<br>".join(f"{quantity}x {link}" for link, quantity in enriched.sources.crafting_results)

        mold_context = {
            "icon": item_image_file(item),
            "name": display_name,
            "value": self._item_window_value(item),
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "ingredients": ingredients,
            "rewards": rewards,
            "station": "",
        }

        mold_template = self.render_template("mold.jinja2", mold_context)
        return f"{item_template}\n\n{mold_template}"

    def _generate_general_page(self, enriched: EnrichedItemData) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(spell, prefix="effect")

        if enriched.proc:
            spell_details["effect_style"] = safe_str(enriched.proc.proc_style)
            spell_details["effect_chance"] = safe_str(enriched.proc.proc_chance)
        else:
            spell_details["effect_style"] = ""
            spell_details["effect_chance"] = ""

        general_context = {
            "icon": item_image_file(item),
            "value": self._item_window_value(item),
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "stack_size": "",
            "disposable": "True" if item.disposable else "",
            **spell_details,
        }

        general_template = self.render_template("general.jinja2", general_context)
        return f"{item_template}\n\n{general_template}"

    # ------------------------------------------------------------------
    # Shared spell/proc display contract
    # ------------------------------------------------------------------

    def _build_spell_details_context(self, spell: Spell | None, prefix: str = "proc") -> dict[str, str]:
        """Build template context for spell details fields using entity attributes directly."""
        empty_context: dict[str, str] = {
            f"{prefix}_spell_icon": "",
            f"{prefix}_spell_name": "",
            f"{prefix}_spell_level": "",
            f"{prefix}_spell_duration_ticks": "",
            f"{prefix}_spell_type": "",
            f"{prefix}_spell_line": "",
            f"{prefix}_target_damage": "",
            f"{prefix}_target_healing": "",
            f"{prefix}_shielding_amt": "",
            f"{prefix}_damage_type": "",
            f"{prefix}_cast_time": "",
            f"{prefix}_cooldown": "",
            f"{prefix}_spell_range": "",
            f"{prefix}_lifetap": "",
            f"{prefix}_group_effect": "",
            f"{prefix}_stun_target": "",
            f"{prefix}_charm_target": "",
            f"{prefix}_root_target": "",
            f"{prefix}_taunt_spell": "",
            f"{prefix}_aggro": "",
            f"{prefix}_status_effect_name": "",
            f"{prefix}_hp": "",
            f"{prefix}_ac": "",
            f"{prefix}_mana": "",
            f"{prefix}_str": "",
            f"{prefix}_dex": "",
            f"{prefix}_end": "",
            f"{prefix}_agi": "",
            f"{prefix}_wis": "",
            f"{prefix}_int": "",
            f"{prefix}_cha": "",
            f"{prefix}_mr": "",
            f"{prefix}_er": "",
            f"{prefix}_pr": "",
            f"{prefix}_vr": "",
            f"{prefix}_movement_speed": "",
            f"{prefix}_damage_shield": "",
            f"{prefix}_haste": "",
            f"{prefix}_percent_lifesteal": "",
            f"{prefix}_atk_roll_modifier": "",
            f"{prefix}_resonate_chance": "",
            f"{prefix}_add_proc_name": "",
            f"{prefix}_add_proc_chance": "",
            f"{prefix}_special_descriptor": "",
            f"{prefix}_xp_bonus": "",
        }

        if spell is None:
            return empty_context

        def bool_str(val: int | None) -> str:
            return "True" if val else ""

        def num_str(val: int | float | None) -> str:
            if val is None or val == 0:
                return ""
            return str(val)

        # add_proc name: use pre-built link on spell entity
        add_proc_name = str(spell.add_proc_link) if spell.add_proc_link else ""

        # status_effect name: use pre-built link on spell entity
        status_effect_name = ""
        if spell.status_effect_link:
            status_effect_name = f"<br>{spell.status_effect_link!s}"

        # Spell display name and icon from entity attributes
        spell_display_name = spell.display_name or spell.spell_name or ""
        spell_icon = picture_file_title("icon", spell.image_name)

        # Wiki link for spell name
        spell_name_link = str(
            AbilityLink(
                page_title=spell.wiki_page_name,
                display_name=spell_display_name,
                image_name=spell.image_name,
                stable_key=spell.stable_key,
            )
        )

        return {
            f"{prefix}_spell_icon": spell_icon,
            f"{prefix}_spell_name": spell_name_link,
            f"{prefix}_spell_level": num_str(spell.required_level),
            f"{prefix}_spell_duration_ticks": num_str(spell.spell_duration_in_ticks),
            f"{prefix}_spell_type": spell.type or "",
            f"{prefix}_spell_line": spell.line or "",
            f"{prefix}_target_damage": num_str(spell.target_damage),
            f"{prefix}_target_healing": num_str(spell.target_healing),
            f"{prefix}_shielding_amt": num_str(spell.shielding_amt),
            f"{prefix}_damage_type": spell.damage_type or "",
            f"{prefix}_cast_time": f"{spell.spell_charge_time / 60.0:.1f}" if spell.spell_charge_time else "",
            f"{prefix}_cooldown": num_str(spell.cooldown),
            f"{prefix}_spell_range": num_str(spell.spell_range),
            f"{prefix}_lifetap": bool_str(spell.lifetap),
            f"{prefix}_group_effect": bool_str(spell.group_effect),
            f"{prefix}_stun_target": bool_str(spell.stun_target),
            f"{prefix}_charm_target": bool_str(spell.charm_target),
            f"{prefix}_root_target": bool_str(spell.root_target),
            f"{prefix}_taunt_spell": bool_str(spell.taunt_spell),
            f"{prefix}_aggro": num_str(spell.aggro),
            f"{prefix}_status_effect_name": status_effect_name,
            f"{prefix}_hp": num_str(spell.hp),
            f"{prefix}_ac": num_str(spell.ac),
            f"{prefix}_mana": num_str(spell.mana),
            f"{prefix}_str": num_str(spell.str_),
            f"{prefix}_dex": num_str(spell.dex),
            f"{prefix}_end": num_str(spell.end_),
            f"{prefix}_agi": num_str(spell.agi),
            f"{prefix}_wis": num_str(spell.wis),
            f"{prefix}_int": num_str(spell.int_),
            f"{prefix}_cha": num_str(spell.cha),
            f"{prefix}_mr": num_str(spell.mr),
            f"{prefix}_er": num_str(spell.er),
            f"{prefix}_pr": num_str(spell.pr),
            f"{prefix}_vr": num_str(spell.vr),
            f"{prefix}_movement_speed": num_str(spell.movement_speed),
            f"{prefix}_damage_shield": num_str(spell.damage_shield),
            f"{prefix}_haste": num_str(spell.haste),
            f"{prefix}_percent_lifesteal": num_str(spell.percent_lifesteal),
            f"{prefix}_atk_roll_modifier": num_str(spell.atk_roll_modifier),
            f"{prefix}_resonate_chance": num_str(spell.resonate_chance),
            f"{prefix}_add_proc_name": add_proc_name,
            f"{prefix}_add_proc_chance": num_str(spell.add_proc_chance),
            f"{prefix}_special_descriptor": spell.special_descriptor or "",
            f"{prefix}_xp_bonus": str(round(spell.xp_bonus * 100))
            if spell.xp_bonus and spell.line == "XPBonus"
            else "",
        }

    # ------------------------------------------------------------------
    # Infobox
    # ------------------------------------------------------------------

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
                    stable_key=sp.stable_key,
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
                    stable_key=sk.stable_key,
                )
            )

        return {
            "title": display_name,
            "stablekey": item.stable_key,
            "icon": item_image_file(item),
            # The infobox shows the renders and the editors' screenshot where
            # their files exist, and the icon otherwise.
            "render": enriched.renders.get(None, ""),
            "render_male": enriched.renders.get("male", ""),
            "render_female": enriched.renders.get("female", ""),
            "screenshot": picture_file_title("screenshot", item.image_name, item.display_name, item.item_name),
            "type": item_type,
            "vendorsource": fold_long_list(vendor_sources),
            "source": fold_long_list(drop_sources),
            "dialogsource": fold_long_list(self._format_givers(enriched)),
            "questsource": quest_rewards_str,
            "craftsource": craft_sources,
            "itemusesource": fold_long_list(self._format_item_uses(enriched)),
            "miningsource": fold_long_list(self._format_mining(enriched)),
            "fishingsource": fold_long_list(self._format_fishing(enriched)),
            "itembagsource": fold_long_list(self._format_item_bags(enriched)),
            "startingsource": self._format_starting_classes(enriched),
            # A flag: Template:Item holds the wording, so one edit changes every page.
            "auctionhousesource": (
                "yes"
                if enriched.sources and any(source.kind == "auction_house" for source in self._acquisitions(enriched))
                else ""
            ),
            "othersource": "",
            "relatedquest": quest_requirements_str,
            "componentfor": fold_long_list(component_for_str),
            "buy": safe_str(item.item_value) if item.item_value else "",
            "sell": safe_str(item.sell_value) if item.sell_value else "",
            "taughtspell": taughtspell,
            "taughtskill": taughtskill,
            "guaranteeddrops": self._format_guaranteed_drops(enriched),
            "droprates": self._format_drop_rates(enriched),
        }

    @staticmethod
    def _acquisitions(enriched: EnrichedItemData) -> tuple[ItemAcquisition, ...]:
        if enriched.sources is None:
            return ()
        if enriched.sources.disposition is not None and enriched.sources.disposition.disposition != "current":
            return ()
        return tuple(fact for fact in enriched.sources.acquisitions if is_actionable_acquisition(fact))

    @staticmethod
    def _link(sources: SourceInfo, key: str | None, fallback: str) -> str:
        link = sources.links.get(key or "")
        return str(link) if link is not None else fallback

    def _condition(self, atom: ProvenanceCondition, sources: SourceInfo) -> str:
        if atom.predicate == "account_state":
            labels: dict[tuple[str | None, str | None], str] = {
                ("account_state:reliquary_claimed", "false"): "before claiming your Reliquary",
                ("account_state:reliquary_claimed", "true"): "after claiming your Reliquary",
            }
            label = labels.get((atom.reference_stable_key, atom.value))
            if label is None:
                raise ValueError("Unsupported canonical account-state display label")
            return "" if atom.phase == "operation_outcome" else label
        reference = self._link(sources, atom.reference_stable_key, "the required condition")
        predicates = {
            "quest_done": f"after {reference}",
            "quest_not_done": f"before completing {reference}",
            "item_held": f"carrying {reference}",
            "key_held": f"carrying {reference}",
            "item_not_owned": f"without {reference}",
            "room_furnished": f"after furnishing room {atom.reference_slot or ''} with {reference}",
            "encounter_won": f"after defeating {reference}",
            "zone_use": f"in {reference}",
            "time_of_day": atom.value or "",
            "quality": f"{atom.value or ''} quality",
            "never": "not available",
        }
        if atom.predicate in predicates:
            return predicates[atom.predicate]
        if atom.predicate == "actor_level":
            actor = {"enemy": "enemy", "player": "player", "sim": "simulated player"}.get(atom.actor or "", "character")
            bounds = []
            if atom.minimum is not None:
                bounds.append(f"{'at least' if atom.minimum_inclusive else 'above'} {atom.minimum:g}")
            if atom.maximum is not None:
                bounds.append(f"{'at most' if atom.maximum_inclusive else 'below'} {atom.maximum:g}")
            return f"{actor} level " + " and ".join(bounds)
        if atom.predicate == "formula_operand":
            return ""
        raise ValueError(f"Unsupported canonical item condition: {atom.predicate}")

    def _conditions(self, atoms: tuple[ProvenanceCondition, ...], sources: SourceInfo) -> str:
        gates: dict[tuple[str, str], dict[int, list[str]]] = {}
        for atom in atoms:
            text = self._condition(atom, sources)
            if text:
                gates.setdefault((atom.scope, atom.gate_key), {}).setdefault(atom.group_index, []).append(text)
        parts = []
        for groups in gates.values():
            alternatives = [" and ".join(texts) for _index, texts in sorted(groups.items())]
            parts.append("(" + " or ".join(alternatives) + ")" if len(alternatives) > 1 else alternatives[0])
        return " and ".join(parts)

    @staticmethod
    def _chance(fact: ItemAcquisition) -> str:
        if fact.probability_min is None or fact.probability_kind not in ("exact", "bounded"):
            return ""
        chance = f"{fact.probability_min:.3g}%"
        if fact.probability_max is not None and fact.probability_max != fact.probability_min:
            chance += f" to {fact.probability_max:.3g}%"
        basis = {
            "per_kill": "per kill",
            "per_use": "per use",
            "per_node": "per node",
            "per_successful_catch": "per catch",
        }.get(fact.probability_basis or "", "")
        return f"{chance} {basis}".strip()

    def _source_entry(self, fact: ItemAcquisition, sources: SourceInfo) -> str:
        fallback = {
            "character_drop": "Enemy drop",
            "common_world_item": "Any enemy with common drops",
            "special_world_drop": "Any enemy",
            "vendor": "Vendor",
            "dialog": "Dialog reward",
            "quest_reward": "Quest reward",
            "item_drop": "Using an item",
            "spell_created": "Using an item",
            "item_conversion": "Item conversion",
            "mining": "Mining",
            "fishing": "Fishing",
            "fishing_bonus": "Any water",
            "item_bag": "Ground pickup",
            "starting_class": "Starting inventory",
            "ui_grant": "Interface grant",
            "internal_equipment": "Simulated-player equipment",
        }.get(fact.kind)
        if fallback is None:
            raise ValueError(f"Unsupported canonical item source: {fact.kind}")
        if fact.kind == "ui_grant":
            fallback = {
                "cosmetic_panel": "Cosmetic panel",
                "planning_table": "Planning table",
            }.get(fact.mechanic or "", fallback)
        entry = self._link(sources, fact.source_stable_key, fallback)
        details = []
        if chance := self._chance(fact):
            details.append(chance)
        if fact.quantity_min is not None:
            quantity = f"{fact.quantity_min:g}"
            if fact.quantity_max is not None and fact.quantity_max != fact.quantity_min:
                quantity += f" to {fact.quantity_max:g}"
            if quantity != "1":
                details.append(f"{quantity} items")
        if conditions := self._conditions(fact.conditions, sources):
            details.append(conditions)
        locations = []
        for location in fact.locations:
            place = self._link(sources, location.zone_stable_key, location.scene or "")
            if condition := self._conditions(location.conditions, sources):
                place = f"{place} ({condition})" if place else condition
            if place and place not in locations:
                locations.append(place)
        if locations:
            details.append("in " + " or ".join(locations))
        elif fact.locations and all(location.relation == "unlocated" for location in fact.locations):
            details.append("location unknown")
        return f"{entry} ({', '.join(details)})" if details else entry

    def _format_sources(self, enriched: EnrichedItemData, kinds: tuple[str, ...]) -> str:
        if enriched.sources is None:
            return ""
        return WIKITEXT_LINE_SEPARATOR.join(
            self._source_entry(fact, enriched.sources)
            for fact in sorted(self._acquisitions(enriched), key=lambda fact: fact.acquisition_key)
            if fact.kind in kinds
        )

    def _format_guaranteed_drops(self, enriched: EnrichedItemData) -> str:
        """A guaranteed pool roll does not guarantee an individual item."""
        if enriched.sources is None:
            return ""
        return "<br>".join(
            self._link(enriched.sources, use.target_stable_key, "Item")
            for use in enriched.sources.uses
            if use.kind == "item_drop"
            and (outcome := enriched.sources.outcomes.get(use.outcome_key or "")) is not None
            and outcome.probability_kind == "exact"
            and outcome.probability_min == 100
        )

    def _format_drop_rates(self, enriched: EnrichedItemData) -> str:
        if enriched.sources is None:
            return ""
        entries = []
        for use in enriched.sources.uses:
            if use.kind != "item_drop":
                continue
            outcome = enriched.sources.outcomes.get(use.outcome_key or "")
            if outcome is None:
                raise ValueError(f"Canonical item-drop use has no outcome: {use.use_key}")
            entry = self._link(enriched.sources, use.target_stable_key, "Item")
            chance = self._chance(outcome)
            entries.append(f"{entry} ({chance})" if chance else entry)
        return "<br>".join(entries)

    def _format_vendor_sources(self, enriched: EnrichedItemData) -> str:
        return self._format_sources(enriched, ("vendor",))

    def _format_drop_sources(self, enriched: EnrichedItemData) -> str:
        return self._format_sources(enriched, ("character_drop", "common_world_item", "special_world_drop"))

    def _format_givers(self, enriched: EnrichedItemData) -> str:
        return self._format_sources(enriched, ("dialog",))

    def _format_item_uses(self, enriched: EnrichedItemData) -> str:
        return self._format_sources(enriched, ("item_drop", "spell_created", "item_conversion", "ui_grant"))

    def _format_mining(self, enriched: EnrichedItemData) -> str:
        return self._format_sources(enriched, ("mining",))

    @staticmethod
    def _fishing_summary_groups(
        sources: SourceInfo,
    ) -> dict[tuple[str, float], tuple[list[ItemAcquisition], list[ItemAcquisition]]]:
        """Group final replacement-only catches while keeping their native evidence distinct."""
        if sources.disposition is not None and sources.disposition.disposition != "current":
            return {}
        bonuses: dict[tuple[str, float], list[ItemAcquisition]] = {}
        for fact in sources.acquisitions:
            if (
                fact.kind == "fishing_bonus"
                and fact.probability_stage == "native_pool"
                and fact.player_access_state == "verified_player"
                and fact.probability_kind == "exact"
                and fact.probability_min is not None
                and fact.probability_min > 0
                and fact.probability_max in (None, fact.probability_min)
                and not fact.conditions
            ):
                bonuses.setdefault((fact.item_stable_key, fact.probability_min), []).append(fact)
        groups: dict[tuple[str, float], tuple[list[ItemAcquisition], list[ItemAcquisition]]] = {}
        for fact in sorted(sources.acquisitions, key=lambda candidate: candidate.acquisition_key):
            if (
                fact.kind != "fishing"
                or fact.probability_stage != "final_acquisition"
                or fact.player_access_state != "verified_player"
                or fact.probability_kind != "exact"
                or fact.probability_min is None
                or fact.probability_max not in (None, fact.probability_min)
                or any(atom.predicate != "time_of_day" for atom in fact.conditions)
                or any(location.conditions for location in fact.locations)
            ):
                continue
            key = (fact.item_stable_key, fact.probability_min)
            if key in bonuses:
                groups.setdefault(key, ([], bonuses[key]))[0].append(fact)
        return groups

    @classmethod
    def _fishing_group_manifest(cls, sources: SourceInfo) -> list[dict[str, object]]:
        return [
            {
                "item_stable_key": item_key,
                "chance": chance,
                "member_acquisition_keys": [fact.acquisition_key for fact in members],
                "native_pool_acquisition_keys": sorted(fact.acquisition_key for fact in native),
            }
            for (item_key, chance), (members, native) in sorted(cls._fishing_summary_groups(sources).items())
        ]

    def _format_fishing(self, enriched: EnrichedItemData) -> str:
        if enriched.sources is None:
            return ""
        groups = self._fishing_summary_groups(enriched.sources)
        grouped_ids = {fact.acquisition_key for members, _native in groups.values() for fact in members}
        entries = [
            self._source_entry(fact, enriched.sources)
            for fact in sorted(self._acquisitions(enriched), key=lambda candidate: candidate.acquisition_key)
            if fact.kind in ("fishing", "fishing_bonus") and fact.acquisition_key not in grouped_ids
        ]
        entries.extend(f"Any water ({chance:.3g}% per catch)" for _item_key, chance in sorted(groups))
        return WIKITEXT_LINE_SEPARATOR.join(entries)

    def _format_item_bags(self, enriched: EnrichedItemData) -> str:
        return self._format_sources(enriched, ("item_bag",))

    def _format_starting_classes(self, enriched: EnrichedItemData) -> str:
        return self._format_sources(enriched, ("starting_class",))

    def _format_quest_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        if enriched.sources is None:
            return ("", "")
        requirements = [
            self._link(enriched.sources, use.target_stable_key, "Quest")
            for use in enriched.sources.uses
            if use.kind == "quest_requirement"
        ]
        return (self._format_sources(enriched, ("quest_reward",)), "<br>".join(requirements))

    def _format_crafting_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        if enriched.sources is None:
            return ("", "")
        active_recipes = {fact.source_stable_key for fact in self._acquisitions(enriched) if fact.kind == "crafting"}
        recipes = [
            " + ".join([str(mold), *(f"{quantity}x {link}" for link, quantity in recipe.materials)])
            for mold, recipe in enriched.sources.recipes
            if mold.stable_key in active_recipes
        ]
        for fact in self._acquisitions(enriched):
            if fact.kind == "crafting" and fact.mechanic == "remove_blessing":
                source = self._link(enriched.sources, fact.source_stable_key, "")
                recipes.append(f"From removing a blessing with {source}" if source else "From removing a blessing")
        components = []
        prefixes = {
            "crafting_material": "",
            "spell_created": "Creates ",
            "item_conversion": "Converts to ",
            "smithing": "Smithing with ",
            "quality_offering": "Offer to ",
        }
        for use in enriched.sources.uses:
            if use.kind in prefixes:
                link = self._link(enriched.sources, use.target_stable_key, "item")
                components.append(prefixes[use.kind] + link)
        return ("<br>".join(recipes), "<br>".join(components))

    def provenance_manifest(self, sources: SourceInfo) -> dict[str, object]:
        """Retain full source identities and typed dimensions outside published articles."""
        acquisition_fields = {
            "character_drop": "source",
            "common_world_item": "source",
            "special_world_drop": "source",
            "vendor": "vendorsource",
            "dialog": "dialogsource",
            "quest_reward": "questsource",
            "crafting": "craftsource",
            "item_drop": "itemusesource",
            "spell_created": "itemusesource",
            "mining": "miningsource",
            "fishing": "fishingsource",
            "fishing_bonus": "fishingsource",
            "auction_house": "auctionhousesource",
            "item_bag": "itembagsource",
            "starting_class": "startingsource",
            "ui_grant": "itemusesource",
            "item_conversion": "itemusesource",
            "internal_equipment": None,
        }
        use_fields = {
            "crafting_material": "componentfor",
            "crafting_recipe": "rewards",
            "quest_requirement": "relatedquest",
            "item_drop": "droprates",
            "spell_created": "componentfor",
            "item_conversion": "componentfor",
            "smithing": "componentfor",
            "quality_offering": "componentfor",
            "zone_restriction": None,
        }
        presentation = {}
        for fact in sources.acquisitions:
            if fact.kind not in acquisition_fields:
                raise ValueError(f"Unsupported canonical item source: {fact.kind}")
            reason = None
            field = acquisition_fields[fact.kind]
            if sources.disposition is not None and sources.disposition.disposition != "current":
                reason = "Reviewed non-current lifecycle content does not advertise acquisition sources."
            elif fact.player_access_state != "verified_player":
                reason = "Only verified player sources are advertised."
            elif fact.probability_stage != "final_acquisition":
                reason = "Native-pool evidence is not an additional final acquisition."
            elif (fact.probability_max is not None and fact.probability_max <= 0) or any(
                atom.predicate == "never" for atom in fact.conditions
            ):
                reason = "Unsatisfiable acquisitions are evidence, not player sources."
            elif field is None:
                reason = "Internal equipment is audit-only."
            presentation[fact.acquisition_key] = {"field": field if reason is None else None, "reason": reason}
        for use in sources.uses:
            if use.kind not in use_fields:
                raise ValueError(f"Unsupported canonical item use: {use.kind}")
            field = use_fields[use.kind]
            presentation[use.use_key] = {
                "field": field,
                "reason": None if field else "The legacy item template has no zone-restriction parameter.",
            }
        manifest: dict[str, object] = {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "disposition": fact_to_dict(sources.disposition) if sources.disposition is not None else None,
            "acquisitions": [fact_to_dict(fact) for fact in sources.acquisitions],
            "outcomes": [fact_to_dict(fact) for _key, fact in sorted(sources.outcomes.items())],
            "uses": [fact_to_dict(fact) for fact in sources.uses],
            "presentation": presentation,
            "fishing_groups": self._fishing_group_manifest(sources),
            "concise_dimensions": (
                "Legacy parameters show concise source and recipe descriptions. Copy, variant, evidence, "
                "probability-stage, quantity-distribution and location identities remain in this offline manifest."
            ),
        }
        self.validate_provenance_manifest(sources, manifest)
        return manifest

    @classmethod
    def validate_provenance_manifest(cls, sources: SourceInfo, manifest: dict[str, object]) -> None:
        """Fail offline coverage when any canonical fact or dimension is lost."""
        expected = {
            "disposition": fact_to_dict(sources.disposition) if sources.disposition is not None else None,
            "acquisitions": [fact_to_dict(fact) for fact in sources.acquisitions],
            "uses": [fact_to_dict(fact) for fact in sources.uses],
            "outcomes": [fact_to_dict(fact) for _key, fact in sorted(sources.outcomes.items())],
            "fishing_groups": cls._fishing_group_manifest(sources),
        }
        for family, facts in expected.items():
            if json.dumps(manifest.get(family), sort_keys=True) != json.dumps(facts, sort_keys=True):
                raise ValueError(f"Legacy wiki provenance coverage differs for {family}")
