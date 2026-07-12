"""Tests for item section generation."""

from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.entities.spell import Spell
from erenshor.domain.value_objects.proc_info import ProcInfo
from erenshor.domain.value_objects.wiki_link import AbilityLink


def test_weapon_page_uses_single_lua_item_tooltip() -> None:
    generator = ItemSectionGenerator()
    item = Item(
        stable_key="item:ember_longsword",
        display_name="Ember Longsword",
        item_name="Ember Longsword",
        required_slot="PrimaryOrSecondary",
        this_weapon_type="OneHandMelee",
        item_value=12500,
    )
    enriched = EnrichedItemData(
        item=item,
        stats=[ItemStats(item_stable_key=item.stable_key, quality="Normal", weapon_dmg=10)],
        classes=[],
    )

    result = generator.generate_template(enriched, "Ember Longsword")

    assert "{{ItemTooltip" in result
    assert "|kind=Weapon" in result
    assert "|damage=10" in result
    assert "|stablekey=" not in result
    assert "{{Item/Weapon" not in result
    assert "{{Fancy-weapon" not in result
    assert result.count("{{ItemTooltip") == 1


def test_weapon_tooltip_args_are_display_ready() -> None:
    """Proc fields carry the legacy display contract: linked spell name,
    .png icon, cast time in seconds, and blanks instead of zero noise."""
    generator = ItemSectionGenerator()
    item = Item(
        stable_key="item:oldenbow",
        display_name="Oldenbow",
        item_name="Oldenbow",
        required_slot="Primary",
        this_weapon_type="TwoHandBow",
        is_bow=1,
        bow_range=25,
        is_wand=0,
        wand_range=1,
        weapon_dly=1.6,
    )
    spell = Spell(
        stable_key="spell:ice_spear",
        spell_name="Ice Spear",
        display_name="Ice Spear",
        wiki_page_name="Ice Spear",
        image_name="Ice Spear",
        required_level=21,
        spell_charge_time=60.0,
        target_damage=1100,
        target_healing=0,
        shielding_amt=0,
        xp_bonus=0.0,
    )
    enriched = EnrichedItemData(
        item=item,
        stats=[ItemStats(item_stable_key=item.stable_key, quality="Normal", weapon_dmg=38)],
        classes=["Stormcaller"],
        proc=ProcInfo(
            proc_link=AbilityLink(page_title="Ice Spear", display_name="Ice Spear", image_name="Ice Spear"),
            description="",
            proc_chance="8",
            proc_style="Attack",
            spell=spell,
        ),
    )

    result = generator.generate_template(enriched, "Oldenbow")

    assert "|image=Oldenbow.png" in result
    assert "|type=Primary - 2-Handed" in result
    assert "|range=25" in result
    assert "|proc_spell_name=[[Ice Spear]]" in result
    assert "|proc_spell_icon=Ice Spear.png" in result
    assert "|proc_cast_time=1.0" in result
    assert "|proc_target_damage=1100" in result
    assert "|proc_target_healing=\n" in result
    assert "|proc_shielding_amt=\n" in result
    assert "|proc_xp_bonus=\n" in result
    assert "|stormcaller=True" in result


def test_general_page_uses_legacy_general_template() -> None:
    generator = ItemSectionGenerator()
    item = Item(
        stable_key="item:magical_bag",
        display_name="Magical Bag",
        item_name="Magical Bag",
        required_slot="General",
        lore="A larger bag.",
        item_value=25,
    )
    enriched = EnrichedItemData(item=item, stats=[], classes=[])

    result = generator.generate_template(enriched, "Magical Bag")

    assert "{{Item/General" in result
    assert "|description=A larger bag." in result
    assert "{{ItemTooltip" not in result
    assert "|stablekey=" not in result
