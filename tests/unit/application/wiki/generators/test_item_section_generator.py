from types import SimpleNamespace

import pytest

from erenshor.application.wiki.generators.field_preservation import FieldPreservationConfig, FieldPreservationHandler
from erenshor.application.wiki.generators.pages.entities import EntityPageGenerator
from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.application.wiki_deploy.link_audit import LinkTargets
from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.item_stats import ItemStats
from erenshor.domain.entities.spell import Spell
from erenshor.domain.value_objects.proc_info import ProcInfo
from erenshor.domain.value_objects.source_info import ObtainedFromInfo, SourceInfo, WorldDropInfo
from erenshor.domain.value_objects.wiki_link import AbilityLink, CharacterLink


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
        stats=[ItemStats(item_stable_key=item.stable_key, quality="Standard", weapon_dmg=10)],
        classes=[],
    )

    result = generator.generate_template(enriched, "Ember Longsword")

    assert "{{ItemTooltip" in result
    assert "|kind=Weapon" in result
    assert "|damage=10" in result
    assert "|stablekey=item:ember_longsword" in result
    assert "{{Item/Weapon" not in result
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
        stats=[ItemStats(item_stable_key=item.stable_key, quality="Standard", weapon_dmg=38)],
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

    assert "|icon=Oldenbow icon.png" in result
    assert "|type=Primary\n" in result
    assert "|two_handed=True" in result
    assert "|range=25" in result
    assert "|proc_spell_name={{AbilityLink|stablekey=spell:ice_spear}}" in result
    assert "|proc_spell_icon=Ice Spear icon.png" in result
    assert "|proc_cast_time=1.0" in result
    assert "|proc_target_damage=1100" in result
    assert "|proc_target_healing=\n" in result
    assert "|proc_shielding_amt=\n" in result
    assert "|proc_xp_bonus=\n" in result


def test_two_handed_melee_keeps_game_label_and_category_flag() -> None:
    item = Item(
        stable_key="item:two_handed_sword",
        item_name="Two-Handed Sword",
        required_slot="Primary",
        this_weapon_type="TwoHandMelee",
        weapon_dly=2,
    )
    enriched = EnrichedItemData(
        item=item,
        stats=[ItemStats(item_stable_key=item.stable_key, quality="Standard", weapon_dmg=20)],
        classes=[],
    )

    result = ItemSectionGenerator().generate_template(enriched, "Two-Handed Sword")

    assert "|type=Primary - 2-Handed" in result
    assert "|two_handed=True" in result


def test_melee_range_matches_game_and_does_not_appear_without_attack_stats() -> None:
    sword = Item(
        stable_key="item:weap - 1 - rusty sword",
        item_name="Rusty Shortsword",
        required_slot="PrimaryOrSecondary",
        this_weapon_type="OneHandMelee",
        weapon_dly=1.25,
    )
    stats = [ItemStats(item_stable_key=sword.stable_key, quality="Standard", weapon_dmg=3)]
    result = ItemSectionGenerator().generate_template(
        EnrichedItemData(item=sword, stats=stats, classes=[]), "Rusty Shortsword"
    )
    assert "|range=1\n" in result

    armor = sword.model_copy(update={"required_slot": "Chest", "weapon_dly": 0})
    no_damage = [ItemStats(item_stable_key=sword.stable_key, quality="Standard", weapon_dmg=0)]
    result = ItemSectionGenerator().generate_template(
        EnrichedItemData(item=armor, stats=no_damage, classes=[]), "Rusty Shortsword"
    )
    assert "|range=\n" in result


def test_click_effect_requires_equipping_only_when_game_flag_is_set() -> None:
    item = Item(
        stable_key="item:back - 42 - wakeweaver",
        item_name="Wakeweaver",
        required_slot="Back",
        item_effect_on_click_stable_key="spell:dru - predator's grace",
        must_be_equipped_to_click=1,
    )
    stats = [ItemStats(item_stable_key=item.stable_key, quality="Standard", ac=100)]
    enriched = EnrichedItemData(item=item, stats=stats, classes=[])
    generator = ItemSectionGenerator()

    assert "|must_equip=True" in generator.generate_template(enriched, "Wakeweaver")
    unflagged = EnrichedItemData(item=item.model_copy(update={"must_be_equipped_to_click": 0}), stats=stats, classes=[])
    assert "|must_equip=\n" in generator.generate_template(unflagged, "Wakeweaver")


def test_item_window_value_uses_no_trade_flag_not_vendor_sell_restriction() -> None:
    generator = ItemSectionGenerator()
    bow = Item(stable_key="item:molorai_bow", item_name="Molorai Bow", required_slot="Primary", item_value=400)
    stats = [ItemStats(item_stable_key=bow.stable_key, quality="Standard", weapon_dmg=23)]
    assert "|value=400\n" in generator.generate_template(
        EnrichedItemData(item=bow, stats=stats, classes=[]), "Molorai Bow"
    )

    restricted = bow.model_copy(update={"item_value": 5000, "no_trade_no_destroy": 1})
    assert "|value=Unsellable\n" in generator.generate_template(
        EnrichedItemData(item=restricted, stats=stats, classes=[]), "Restricted Bow"
    )

    vendor_only = bow.model_copy(update={"player_cannot_sell": 1})
    assert "|value=400\n" in generator.generate_template(
        EnrichedItemData(item=vendor_only, stats=stats, classes=[]), "Vendor Restricted Bow"
    )

    wakeweaver = Item(stable_key="item:wakeweaver", item_name="Wakeweaver", required_slot="Back", item_value=0)
    assert "|value=Unsellable\n" in generator.generate_template(
        EnrichedItemData(item=wakeweaver, stats=stats, classes=[]), "Wakeweaver"
    )


def _proc_generator() -> EntityPageGenerator:
    generator = object.__new__(EntityPageGenerator)
    generator.context = SimpleNamespace(
        spell_repo=SimpleNamespace(
            get_spell_by_stable_key=lambda key: Spell(
                stable_key=key,
                spell_name=key,
                display_name=key,
                wiki_page_name=key,
                image_name=key,
            )
        )
    )
    return generator


def test_weapon_proc_trigger_follows_the_item_window() -> None:
    generator = _proc_generator()

    def style(required_slot: str, shield: int) -> str:
        item = Item(
            stable_key=f"item:{required_slot.lower()}",
            item_name=required_slot,
            required_slot=required_slot,
            shield=shield,
            weapon_proc_on_hit_stable_key="spell:stun",
            weapon_proc_chance=10,
        )
        proc = generator._extract_proc(item)
        assert proc is not None
        return proc.proc_style

    assert style("Primary", 0) == "Attack"
    assert style("Secondary", 1) == "Bash"
    assert style("Bracer", 0) == "Cast"

    ring = Item(
        stable_key="item:proc_ring",
        item_name="Proc Ring",
        required_slot="Ring",
        weapon_proc_on_hit_stable_key="spell:stun",
        weapon_proc_chance=10,
    )
    with pytest.raises(ValueError, match="item:proc_ring: the item window shows no trigger"):
        generator._extract_proc(ring)


def test_item_effect_selection_matches_game_click_priority() -> None:
    generator = _proc_generator()
    item = Item(
        stable_key="item:helmet_of_clarity",
        display_name="Helmet of Clarity",
        item_name="Helmet of Clarity",
        item_effect_on_click_stable_key="spell:meditative_trance",
        worn_effect_stable_key="spell:flow",
    )

    proc = generator._extract_proc(item)

    assert proc is not None
    assert proc.proc_style == "Activatable"
    assert proc.spell is not None
    assert proc.spell.stable_key == "spell:meditative_trance"

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
    assert "|stablekey=item:magical_bag" in result


@pytest.mark.parametrize("eligible", [False, True])
@pytest.mark.parametrize("is_auctionable", [0, 1])
def test_auction_house_row_depends_on_sim_listing_source_not_player_auctionability(
    eligible: bool, is_auctionable: int
) -> None:
    item = Item(stable_key="item:test", item_name="Test", is_auctionable=is_auctionable)
    enriched = EnrichedItemData(
        item=item,
        stats=[],
        classes=[],
        sources=SourceInfo(
            obtained_from=[ObtainedFromInfo(source_type="auction_house", source_key=None)] if eligible else []
        ),
    )

    result = ItemSectionGenerator().generate_template(enriched, "Test")

    if eligible:
        assert result.count("|auctionhousesource=yes\n") == 1
    else:
        assert "|auctionhousesource=" not in result

    fetched = "{{Item|stablekey=item:test|title=Test|auctionhousesource=Editor text}}"
    merged = (
        FieldPreservationHandler(FieldPreservationConfig(link_targets=LinkTargets(())))
        .merge_templates(fetched, result, ["Item"])
        .text
    )
    assert "Editor text" not in merged
    if eligible:
        assert "|auctionhousesource=yes" in merged
    else:
        assert "auctionhousesource" not in merged


def test_item_source_lists_world_drops_with_level_gate_and_small_chances() -> None:
    """World drops name no character, keep their level gate, and show the game's chance down to 0.002%."""
    item = Item(stable_key="item:balance", display_name="Crystallized Balance", item_name="Crystallized Balance")
    enriched = EnrichedItemData(
        item=item,
        stats=[],
        classes=[],
        sources=SourceInfo(
            world_drops=[
                WorldDropInfo(probability=0.05, min_level_exclusive=30),
                WorldDropInfo(probability=0.625, min_level_exclusive=0),
                WorldDropInfo(probability=0.002, min_level_exclusive=0),
            ]
        ),
    )

    result = ItemSectionGenerator().generate_template(enriched, "Crystallized Balance")

    assert (
        "|source=Any enemy above level 30 (0.05% per kill)<br>Any enemy (0.625% per kill)"
        "<br>Any enemy (0.002% per kill)\n"
    ) in result


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected"),
    [(0.123, 0.987, "0.1\u20131.0%"), (0.123, 0.149, "0.1%"), (0.5, 0.5, "0.5%")],
)
def test_common_world_item_drop_source_formats_range_at_one_decimal(
    minimum: float, maximum: float, expected: str
) -> None:
    item = Item(stable_key="item:test_food", item_name="Test Food")
    enriched = EnrichedItemData(
        item=item,
        stats=[],
        classes=[],
        sources=SourceInfo(
            obtained_from=[
                ObtainedFromInfo(
                    source_type="common_world_item",
                    source_key=None,
                    probability=minimum,
                    probability_max=maximum,
                )
            ]
        ),
    )

    result = ItemSectionGenerator().generate_template(enriched, "Test Food")

    assert f"|source=Any enemy with common drops ({expected} per kill)\n" in result
    assert "mw-collapsible" not in result


def test_common_world_item_source_survives_folding_alongside_named_droppers() -> None:
    item = Item(stable_key="item:test_food", item_name="Test Food")
    droppers = [
        (
            CharacterLink(
                page_title=f"Enemy {index}",
                display_name=f"Enemy {index}",
                stable_key=f"character:enemy_{index}",
            ),
            10.0,
        )
        for index in range(7)
    ]
    enriched = EnrichedItemData(
        item=item,
        stats=[],
        classes=[],
        sources=SourceInfo(
            drops=droppers,
            obtained_from=[
                ObtainedFromInfo(
                    source_type="common_world_item",
                    source_key=None,
                    probability=0.1,
                    probability_max=0.9,
                )
            ],
        ),
    )

    result = ItemSectionGenerator().generate_template(enriched, "Test Food")

    assert 'data-expandtext="3 more"' in result
    assert result.count("Any enemy with common drops (0.1\u20130.9% per kill)") == 1
    assert "Any enemy with common drops (0.1\u20130.9% per kill)</div>" in result
    for link, _ in droppers:
        assert result.count(str(link)) == 1
