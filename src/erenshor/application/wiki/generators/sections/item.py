"""Item section generator for wiki content.

This module generates MediaWiki template wikitext for individual items including
weapons, armor, consumables, and other item types.

This section generator produces templates for single items. Multi-entity page
assembly is handled by PageGenerator classes.

Template structure:
- General items: {{Item}} template + category tags
- Weapons: {{Item}} + 3x {{Item/Weapon}} (Normal/Blessed/Godly) + category tags
- Armor: {{Item}} + 3x {{Item/Armor}} (Normal/Blessed/Godly) + category tags
- Charms: {{Item}} + {{Item/Charm}} + category tags
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import format_description, safe_str
from erenshor.application.wiki.generators.item_type_display import build_item_types
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase
from erenshor.domain.entities.item_kind import ItemKind, classify_item_kind
from erenshor.shared.game_constants import LONG_NAME_FONT_SIZE, LONG_NAME_THRESHOLD

if TYPE_CHECKING:
    from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
    from erenshor.domain.enriched_data.item import EnrichedItemData
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.domain.entities.spell import Spell


class ItemSectionGenerator(SectionGeneratorBase):
    """Generator for item wiki sections.

    Generates template wikitext for a SINGLE item entity. All name/page resolution
    uses direct entity attribute access and pre-built WikiLink objects from
    SourceInfo — no resolver.

    Multi-entity page assembly is handled by PageGenerator classes, not here.
    """

    def __init__(self, class_display: ClassDisplayNameService) -> None:
        super().__init__()
        self._class_display = class_display

    def generate_template(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate template wikitext for a single item."""
        item = enriched.item
        logger.debug(f"Generating template for item: {item.item_name} (kind: {self._classify(item)})")

        kind = self._classify(item)

        if kind == ItemKind.WEAPON:
            template_wikitext = self._generate_weapon_page(enriched, page_title)
        elif kind == ItemKind.ARMOR:
            template_wikitext = self._generate_armor_page(enriched, page_title)
        elif kind == ItemKind.CHARM:
            template_wikitext = self._generate_charm_page(enriched, page_title)
        elif kind == ItemKind.AURA:
            template_wikitext = self._generate_aura_page(enriched, page_title)
        elif kind == ItemKind.SPELL_SCROLL:
            template_wikitext = self._generate_spellscroll_page(enriched, page_title)
        elif kind == ItemKind.SKILL_BOOK:
            template_wikitext = self._generate_skillbook_page(enriched, page_title)
        elif kind == ItemKind.CONSUMABLE:
            template_wikitext = self._generate_consumable_page(enriched, page_title)
        elif kind == ItemKind.MOLD:
            template_wikitext = self._generate_mold_page(enriched, page_title)
        else:
            template_wikitext = self._generate_general_page(enriched, page_title)

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

    def _generate_aura_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        image_name = item.image_name or display_name

        spell_details = self._build_spell_details_context(enriched.aura_spell, prefix="aura")

        aura_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            **spell_details,
        }

        aura_template = self.render_template("aura.jinja2", aura_context)
        return f"{item_template}\n\n{aura_template}"

    def _generate_spellscroll_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        spell = enriched.taught_spell

        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        image_name = item.image_name or display_name

        spell_classes = enriched.taught_spell_classes
        required_level = str(spell.required_level) if spell and spell.required_level else ""

        def class_level(class_name: str) -> str:
            return required_level if class_name in spell_classes else ""

        spellscroll_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
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

    def _generate_skillbook_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        skill = enriched.taught_skill

        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        image_name = item.image_name or display_name

        def level_str(val: int | None) -> str:
            if val is None or val == 0:
                return ""
            return str(val)

        skillbook_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
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

    def _generate_consumable_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        image_name = item.image_name or display_name

        effect_spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(effect_spell, prefix="effect")

        consumable_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "disposable": "True" if item.disposable else "",
            **spell_details,
        }

        consumable_template = self.render_template("consumable.jinja2", consumable_context)
        return f"{item_template}\n\n{consumable_template}"

    def _generate_mold_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        image_name = item.image_name or display_name

        ingredients = ""
        rewards = ""
        if enriched.sources:
            ingredient_links = [f"{quantity}x {link!s}" for link, quantity in enriched.sources.recipe_ingredients]
            ingredients = "<br>".join(ingredient_links)

            if enriched.sources.crafting_results:
                link, _quantity = enriched.sources.crafting_results[0]
                rewards = str(link)

        mold_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "ingredients": ingredients,
            "rewards": rewards,
            "station": "",
        }

        mold_template = self.render_template("mold.jinja2", mold_context)
        return f"{item_template}\n\n{mold_template}"

    def _generate_general_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        display_name = item.display_name or item.item_name or ""
        image_name = item.image_name or display_name

        spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(spell, prefix="effect")

        if enriched.proc:
            spell_details["effect_style"] = enriched.proc.proc_style
            spell_details["effect_chance"] = enriched.proc.proc_chance
        else:
            spell_details["effect_style"] = ""
            spell_details["effect_chance"] = ""

        general_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "value": safe_str(item.item_value) if item.item_value else "",
            "stack_size": "",
            "disposable": "True" if item.disposable else "",
            **spell_details,
        }

        general_template = self.render_template("general.jinja2", general_context)
        return f"{item_template}\n\n{general_template}"

    def _generate_weapon_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        stats = enriched.stats
        if not stats:
            raise ValueError(
                f"Weapon '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)
        fancy_templates = [self._build_fancy_weapon(enriched, page_title, stat) for stat in stats]
        fancy_table = self._format_fancy_table(fancy_templates)
        return f"{item_template}\n\n{fancy_table}"

    def _generate_armor_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        item = enriched.item
        stats = enriched.stats
        if not stats:
            raise ValueError(
                f"Armor '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)
        fancy_templates = [self._build_fancy_armor(enriched, page_title, stat) for stat in stats]
        fancy_table = self._format_fancy_table(fancy_templates)
        return f"{item_template}\n\n{fancy_table}"

    def _generate_charm_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        stats = enriched.stats
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)
        if stats:
            charm_stat = stats[0]
            charm_context = self._build_charm_context(enriched, page_title, charm_stat)
            charm_template = self.render_template("charm.jinja2", charm_context)
            return f"{item_template}\n\n{charm_template}"
        return item_template

    def _format_item_name_for_fancy_template(self, display_name: str) -> str:
        if len(display_name) > LONG_NAME_THRESHOLD:
            return f'<span style="font-size:{LONG_NAME_FONT_SIZE}">{display_name}</span>'
        return display_name

    def _weapon_type_display(self, required_slot: str | None, this_weapon_type: str | None) -> str:
        slot = (required_slot if required_slot is not None else "").strip()
        if slot == "PrimaryOrSecondary":
            slot = "Primary or Secondary"
        weapon_kind = (this_weapon_type if this_weapon_type is not None else "").strip()
        two_handed = weapon_kind in ("TwoHandMelee", "TwoHandStaff", "TwoHandBow")
        if two_handed:
            slot += " - 2-Handed"
        return slot

    def _get_weapon_range(self, item: Item) -> str:
        if item.is_wand and item.wand_range and item.wand_range > 0:
            return str(item.wand_range)
        if item.is_bow and item.bow_range and item.bow_range > 0:
            return str(item.bow_range)
        return ""

    def _build_item_infobox_context(self, enriched: EnrichedItemData, page_title: str) -> dict[str, str]:
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
            wiki = sp.wiki_page_name
            disp = sp.display_name or sp.spell_name or ""
            if wiki:
                taughtspell = f"[[{wiki}|{disp}]]" if disp != wiki else f"[[{wiki}]]"
            else:
                taughtspell = disp

        # Taught skill link
        taughtskill = ""
        if item.teach_skill_stable_key and enriched.taught_skill:
            sk = enriched.taught_skill
            wiki = sk.wiki_page_name
            disp = sk.display_name or sk.skill_name or ""
            if wiki:
                taughtskill = f"[[{wiki}|{disp}]]" if disp != wiki else f"[[{wiki}]]"
            else:
                taughtskill = disp

        guaranteed_drops = self._format_guaranteed_drops(enriched)
        drop_rates = self._format_drop_rates(enriched)

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
            "guaranteeddrops": guaranteed_drops,
            "droprates": drop_rates,
        }

    def _build_fancy_weapon(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> str:
        item = enriched.item
        tier = {"Normal": 0, "Blessed": 1, "Godly": 2}.get(stat.quality, 0)
        weapon_type = self._weapon_type_display(item.required_slot, item.this_weapon_type)
        class_flags = self._build_class_flags(enriched.classes)
        display_name = item.display_name or item.item_name or ""

        spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(spell, prefix="proc")

        if enriched.proc:
            spell_details["proc_style"] = enriched.proc.proc_style
            spell_details["proc_chance"] = enriched.proc.proc_chance
        else:
            spell_details["proc_style"] = ""
            spell_details["proc_chance"] = ""

        return self.render_template(
            "weapon.jinja2",
            {
                "image": f"{page_title}.png",
                "name": self._format_item_name_for_fancy_template(display_name),
                "type": weapon_type,
                "relic": "True" if item.relic else "",
                "str": safe_str(stat.str_),
                "end": safe_str(stat.end_),
                "dex": safe_str(stat.dex),
                "agi": safe_str(stat.agi),
                "int": safe_str(stat.int_),
                "wis": safe_str(stat.wis),
                "cha": safe_str(stat.cha),
                "res": safe_str(stat.res),
                "damage": safe_str(stat.weapon_dmg) if stat.weapon_dmg else "",
                "delay": safe_str(item.weapon_dly) if item.weapon_dly else "",
                "range": self._get_weapon_range(item),
                "health": safe_str(stat.hp),
                "mana": safe_str(stat.mana),
                "armor": safe_str(stat.ac),
                "magic": safe_str(stat.mr),
                "poison": safe_str(stat.pr),
                "elemental": safe_str(stat.er),
                "void": safe_str(stat.vr),
                "description": format_description(safe_str(item.lore)) if item.lore else "",
                **class_flags,
                **spell_details,
                "tier": str(tier),
            },
        )

    def _build_fancy_armor(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> str:
        item = enriched.item
        tier = {"Normal": 0, "Blessed": 1, "Godly": 2}.get(stat.quality, 0)
        slot = safe_str(item.required_slot)
        class_flags = self._build_class_flags(enriched.classes)
        display_name = item.display_name or item.item_name or ""

        spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(spell, prefix="proc")

        if enriched.proc:
            spell_details["proc_style"] = enriched.proc.proc_style
            spell_details["proc_chance"] = enriched.proc.proc_chance
        else:
            spell_details["proc_style"] = ""
            spell_details["proc_chance"] = ""

        return self.render_template(
            "armor.jinja2",
            {
                "image": f"{page_title}.png",
                "name": self._format_item_name_for_fancy_template(display_name),
                "type": "",
                "slot": slot,
                "relic": "True" if item.relic else "",
                "str": safe_str(stat.str_),
                "end": safe_str(stat.end_),
                "dex": safe_str(stat.dex),
                "agi": safe_str(stat.agi),
                "int": safe_str(stat.int_),
                "wis": safe_str(stat.wis),
                "cha": safe_str(stat.cha),
                "res": safe_str(stat.res),
                "health": safe_str(stat.hp),
                "mana": safe_str(stat.mana),
                "armor": safe_str(stat.ac),
                "magic": safe_str(stat.mr),
                "poison": safe_str(stat.pr),
                "elemental": safe_str(stat.er),
                "void": safe_str(stat.vr),
                "description": format_description(safe_str(item.lore)) if item.lore else "",
                **class_flags,
                **spell_details,
                "tier": str(tier),
            },
        )

    def _build_charm_context(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> dict[str, str]:
        item = enriched.item

        def format_scaling(value: float | None) -> str:
            if value is None or value == 0.0:
                return ""
            return str(round(value))

        display_name = item.display_name or item.item_name or ""
        image_name = item.image_name or display_name

        return {
            "image": f"{image_name}.png" if image_name else f"{page_title}.png",
            "name": display_name,
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
            **self._build_class_flags(enriched.classes),
        }

    def _build_class_flags(self, class_names: list[str]) -> dict[str, str]:
        class_set = set(class_names)
        known_classes = self._class_display.get_all_internal_names()
        return {name.lower(): "True" if name in class_set else "" for name in known_classes}

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
        image_name = spell.image_name
        spell_icon = f"{image_name}.png" if image_name else ""

        # Wiki link for spell name
        wiki = spell.wiki_page_name
        if wiki:
            spell_name_link = f"[[{wiki}|{spell_display_name}]]" if spell_display_name != wiki else f"[[{wiki}]]"
        else:
            spell_name_link = spell_display_name

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

    def _format_fancy_table(self, fancy_templates: list[str]) -> str:
        columns = "\n!".join(fancy_templates)
        return f"{{|\n!{columns}\n|}}"

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

    def _format_guaranteed_drops(self, enriched: EnrichedItemData) -> str:
        """Format guaranteed drop pool from pre-built ItemLink objects."""
        if not enriched.sources or not enriched.sources.item_drops:
            return ""
        items_with_names = [
            (link.display_name.lower(), str(link))
            for link, _ in enriched.sources.item_drops
            if link.page_title is not None
        ]
        items_with_names.sort(key=lambda x: x[0])
        return "<br>".join(link for _, link in items_with_names)

    def _format_drop_rates(self, enriched: EnrichedItemData) -> str:
        """Format drop rates from pre-built ItemLink objects with probabilities."""
        if not enriched.sources or not enriched.sources.item_drops:
            return ""
        links = [
            f"{link!s} ({probability:.0f}%)"
            for link, probability in enriched.sources.item_drops
            if link.page_title is not None
        ]
        return "<br>".join(links)
