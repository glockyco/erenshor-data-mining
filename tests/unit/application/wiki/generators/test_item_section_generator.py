from dataclasses import replace
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
from erenshor.domain.value_objects.crafting_recipe import CraftingRecipe
from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
    fact_to_dict,
)
from erenshor.domain.value_objects.proc_info import ProcInfo
from erenshor.domain.value_objects.source_info import SourceInfo
from erenshor.domain.value_objects.wiki_link import AbilityLink, CharacterLink, ItemLink, QuestLink, ZoneLink


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


def _source(
    key: str,
    item: str,
    kind: str,
    source: str | None = None,
    chance: float | None = None,
) -> ItemAcquisition:
    return ItemAcquisition(
        key,
        item,
        kind,
        source,
        probability_kind="unknown" if chance is None else "exact",
        probability_min=chance,
        probability_max=chance,
        probability_basis="per_kill",
    )


@pytest.mark.parametrize("eligible", [False, True])
@pytest.mark.parametrize("is_auctionable", [0, 1])
def test_auction_house_row_depends_on_canonical_listing_source(
    eligible: bool,
    is_auctionable: int,
) -> None:
    item = Item(stable_key="item:test", item_name="Test", is_auctionable=is_auctionable)
    enriched = EnrichedItemData(
        item=item,
        stats=[],
        classes=[],
        sources=SourceInfo(
            acquisitions=(
                (_source("acq:auction", item.stable_key, "auction_house", "mechanic:auction_house"),)
                if eligible
                else ()
            )
        ),
    )
    result = ItemSectionGenerator().generate_template(enriched, "Test")
    assert ("|auctionhousesource=yes\n" in result) == eligible
    fetched = "{{Item|stablekey=item:test|title=Test|auctionhousesource=Editor text}}"
    merged = (
        FieldPreservationHandler(FieldPreservationConfig(link_targets=LinkTargets(())))
        .merge_templates(fetched, result, ["Item"])
        .text
    )
    assert "Editor text" not in merged
    assert ("|auctionhousesource=yes" in merged) == eligible


def test_item_source_preserves_small_world_chances_and_enemy_gate() -> None:
    item = Item(stable_key="item:balance", item_name="Crystallized Balance")
    facts = (
        replace(
            _source("acq:1", item.stable_key, "special_world_drop", chance=0.05),
            conditions=(
                ProvenanceCondition("level", 0, 0, "actor_level", actor="enemy", minimum=30, minimum_inclusive=False),
            ),
        ),
        _source("acq:2", item.stable_key, "special_world_drop", chance=0.625),
        _source("acq:3", item.stable_key, "special_world_drop", chance=0.002),
    )
    enriched = EnrichedItemData(item=item, stats=[], classes=[], sources=SourceInfo(acquisitions=facts))
    result = ItemSectionGenerator().generate_template(enriched, "Crystallized Balance")
    assert "0.05% per kill" in result
    assert "enemy level above 30" in result
    assert "0.625% per kill" in result
    assert "0.002% per kill" in result


def test_common_world_bounds_and_distinct_copy_sources_survive_folding() -> None:
    item = Item(stable_key="item:food", item_name="Food")
    links = {
        f"character:enemy_{index}": CharacterLink(
            f"Enemy {index}", f"Enemy {index}", stable_key=f"character:enemy_{index}"
        )
        for index in range(7)
    }
    facts = (
        *tuple(
            replace(_source(f"acq:{index}", item.stable_key, "character_drop", key, 10), source_copy_stable_key=key)
            for index, key in enumerate(links)
        ),
        replace(
            _source("acq:world", item.stable_key, "common_world_item", chance=0.1),
            probability_kind="bounded",
            probability_max=0.9,
        ),
    )
    sources = SourceInfo(acquisitions=facts, links=links)
    enriched = EnrichedItemData(item=item, stats=[], classes=[], sources=sources)
    generator = ItemSectionGenerator()
    result = generator.generate_template(enriched, "Food")
    assert 'data-expandtext="3 more"' in result
    assert result.count("Any enemy with common drops (0.1% to 0.9% per kill)") == 1
    for link in links.values():
        assert result.count(str(link)) == 1
    assert generator.provenance_manifest(sources)["acquisitions"] == [fact_to_dict(fact) for fact in facts]


def test_vendor_gate_alternatives_and_furniture_location_are_not_erased() -> None:
    item = Item(stable_key="item:test", item_name="Test")
    links = {
        "character:vendor": CharacterLink("Vendor", "Vendor", stable_key="character:vendor"),
        "quest:a": QuestLink("Quest A", "Quest A", stable_key="quest:a"),
        "quest:b": QuestLink("Quest B", "Quest B", stable_key="quest:b"),
        "item:furniture": ItemLink("Furniture", "Furniture", stable_key="item:furniture"),
        "zone:hall": ZoneLink("Hall", "Hall", stable_key="zone:hall"),
    }
    fact = replace(
        _source("acq:vendor", item.stable_key, "vendor", "character:vendor"),
        conditions=(
            ProvenanceCondition("unlock", 0, 0, "quest_done", "quest:a"),
            ProvenanceCondition("unlock", 1, 0, "quest_done", "quest:b"),
        ),
        locations=(
            ProvenanceLocation(
                "placement:room",
                "spawn",
                zone_stable_key="zone:hall",
                conditions=(ProvenanceCondition("furniture", 0, 0, "room_furnished", "item:furniture", "L1"),),
            ),
        ),
    )
    sources = SourceInfo(acquisitions=(fact,), links=links)
    result = ItemSectionGenerator().generate_template(
        EnrichedItemData(item=item, stats=[], classes=[], sources=sources),
        "Test",
    )
    assert "after {{QuestLink|stablekey=quest:a}} or after {{QuestLink|stablekey=quest:b}}" in result
    assert "after furnishing room L1 with {{ItemLink|stablekey=item:furniture}}" in result


def test_fishing_keeps_day_night_final_rates_and_hides_native_pool_evidence() -> None:
    item = Item(stable_key="item:fish", item_name="Fish")
    facts = tuple(
        replace(
            _source(f"acq:{period}", item.stable_key, "fishing", chance=chance),
            probability_basis="per_successful_catch",
            conditions=(ProvenanceCondition("time", 0, 0, "time_of_day", value=period),),
        )
        for period, chance in (("day", 10), ("night", 30))
    )
    native = replace(
        facts[0],
        acquisition_key="acq:native",
        probability_stage="native_pool",
        probability_min=99,
        probability_max=99,
    )
    sources = SourceInfo(acquisitions=(*facts, native))
    result = ItemSectionGenerator().generate_template(
        EnrichedItemData(item=item, stats=[], classes=[], sources=sources),
        "Fish",
    )
    assert "10% per catch, day" in result
    assert "30% per catch, night" in result
    assert "99%" not in result
    assert len(ItemSectionGenerator().provenance_manifest(sources)["acquisitions"]) == 3


def test_article_assembler_enumerates_every_canonical_recipe_without_raw_sql() -> None:
    item = Item(stable_key="item:reward", item_name="Reward")
    mold_a = ItemLink("Mold A", "Mold A", stable_key="item:mold_a")
    mold_b = ItemLink("Mold B", "Mold B", stable_key="item:mold_b")
    material_a = ItemLink("Ore A", "Ore A", stable_key="item:ore_a")
    material_b = ItemLink("Ore B", "Ore B", stable_key="item:ore_b")
    facts = [
        _source("acq:a", item.stable_key, "crafting", "item:mold_a"),
        _source("acq:b", item.stable_key, "crafting", "item:mold_b"),
    ]
    recipes = {
        "item:mold_a": CraftingRecipe(materials=[(material_a, 2)]),
        "item:mold_b": CraftingRecipe(materials=[(material_b, 3)]),
    }
    generator = EntityPageGenerator.__new__(EntityPageGenerator)
    generator.item_generator = ItemSectionGenerator()
    generator.item_provenance_manifest = {}
    generator._item_source_links = {"item:mold_a": mold_a, "item:mold_b": mold_b}
    generator.context = SimpleNamespace(
        item_provenance_repo=SimpleNamespace(
            get_acquisitions=lambda _key: facts,
            get_uses=lambda _key: [],
            get_disposition=lambda key: ItemDisposition(
                key,
                "current",
                reason="Current exported identity",
                evidence="reviewed lifecycle input",
                current_pages=("Reward",),
                former_pages=("Former Reward",),
            ),
        ),
        item_repo=SimpleNamespace(get_crafting_recipe=lambda key: recipes.get(key)),
    )
    sources = generator._assemble_source_info(item)
    assert sources.disposition is not None
    assert generator.item_provenance_manifest[item.stable_key]["disposition"] == fact_to_dict(sources.disposition)
    enriched = EnrichedItemData(item=item, stats=[], classes=[], sources=sources)
    text = generator.item_generator._format_crafting_sources(enriched)[0]
    assert str(mold_a) in text and str(mold_b) in text
    assert f"2x {material_a}" in text and f"3x {material_b}" in text
    assert generator.item_provenance_manifest[item.stable_key]["acquisitions"] == [fact_to_dict(fact) for fact in facts]


def test_container_pool_guarantee_does_not_guarantee_its_individual_item() -> None:
    item = Item(stable_key="item:container", item_name="Container")
    outcome = replace(_source("acq:drop", "item:reward", "item_drop", item.stable_key, 25), guarantee_scope="pool")
    use = ItemUse("use:drop", item.stable_key, "item:reward", "item_drop", outcome_key=outcome.acquisition_key)
    sources = SourceInfo(
        uses=(use,),
        outcomes={outcome.acquisition_key: outcome},
        links={"item:reward": ItemLink("Reward", "Reward", stable_key="item:reward")},
    )
    enriched = EnrichedItemData(item=item, stats=[], classes=[], sources=sources)
    generator = ItemSectionGenerator()
    assert generator._format_guaranteed_drops(enriched) == ""
    assert "25%" in generator._format_drop_rates(enriched)


@pytest.mark.parametrize(
    "dimension",
    [
        "conditions",
        "locations",
        "probability_min",
        "quantity_min",
        "source_stable_key",
        "source_copy_stable_key",
    ],
)
def test_article_provenance_coverage_rejects_lost_fact_dimensions(dimension: str) -> None:
    fact = replace(
        _source("acq:copy", "item:reward", "vendor", "character:vendor"),
        source_copy_stable_key="character:vendor_copy",
        quantity_min=2,
        quantity_max=2,
        quantity_kind="exact",
        conditions=(ProvenanceCondition("quest", 0, 0, "quest_done", "quest:unlock"),),
        locations=(ProvenanceLocation("unlocated:vendor", "unlocated"),),
        evidence=(ProvenanceEvidence("vendor_offers", "copy,item,quest"),),
    )
    sources = SourceInfo(acquisitions=(fact,))
    generator = ItemSectionGenerator()
    manifest = generator.provenance_manifest(sources)
    del manifest["acquisitions"][0][dimension]
    with pytest.raises(ValueError, match="coverage differs"):
        generator.validate_provenance_manifest(sources, manifest)


def test_article_provenance_coverage_rejects_lost_source_kind() -> None:
    sources = SourceInfo(acquisitions=(_source("acq:grant", "item:token", "ui_grant"),))
    generator = ItemSectionGenerator()
    manifest = generator.provenance_manifest(sources)
    manifest["acquisitions"] = []
    with pytest.raises(ValueError, match="coverage differs"):
        generator.validate_provenance_manifest(sources, manifest)


def test_native_ui_source_has_familiar_label_and_unconfirmed_paths_are_not_advertised() -> None:
    item = Item(stable_key="item:token", item_name="Token")
    fact = replace(
        _source("acq:ui", item.stable_key, "ui_grant", "ui:scene:path:ReplenishTMOGHide"),
        mechanic="cosmetic_panel",
    )
    sources = SourceInfo(
        acquisitions=(
            fact,
            replace(fact, acquisition_key="acq:unconfirmed", player_access_state="unconfirmed_player"),
        )
    )
    result = ItemSectionGenerator().generate_template(
        EnrichedItemData(item=item, stats=[], classes=[], sources=sources),
        "Token",
    )
    assert result.count("Cosmetic panel") == 1
    assert "ReplenishTMOGHide" not in result
    assert "ui:scene:path" not in result


def _global_fishing_sources() -> SourceInfo:
    item_key = "item:map"
    facts = [
        replace(
            _source(f"acq:water:{water}:{period}", item_key, "fishing", f"water:{water}", 1.25),
            probability_basis="per_successful_catch",
            conditions=(ProvenanceCondition("time", 0, 0, "time_of_day", value=period),),
            locations=(
                ProvenanceLocation(
                    f"location:{water}",
                    "fixed",
                    zone_stable_key=f"zone:{water}",
                ),
            ),
        )
        for water in range(31)
        for period in ("day", "night")
    ]
    facts.extend(
        replace(
            _source(f"acq:brake:{period}", item_key, "fishing", "water:brake_topright", chance),
            probability_basis="per_successful_catch",
            conditions=(ProvenanceCondition("time", 0, 0, "time_of_day", value=period),),
            locations=(
                ProvenanceLocation(
                    "location:brake",
                    "fixed",
                    zone_stable_key="zone:brake",
                ),
            ),
        )
        for period, chance in (("day", 7.1875), ("night", 7.583333))
    )
    facts.append(
        replace(
            _source("acq:global", item_key, "fishing_bonus", chance=1.25),
            probability_stage="native_pool",
            probability_basis="per_successful_catch",
        )
    )
    return SourceInfo(
        acquisitions=tuple(facts),
        links={"zone:brake": ZoneLink("Brake", "Brake", stable_key="zone:brake")},
    )


def test_global_fishing_roll_has_one_summary_while_native_overlap_keeps_local_time_rates() -> None:
    sources = _global_fishing_sources()
    item = Item(stable_key="item:map", item_name="Map")
    text = ItemSectionGenerator()._format_fishing(
        EnrichedItemData(item=item, stats=[], classes=[], sources=sources),
    )
    assert text.count("Any water (1.25% per catch)") == 1
    assert text.count("1.25%") == 1
    assert "7.19% per catch, day" in text
    assert "7.58% per catch, night" in text
    assert text.count("{{ZoneLink|stablekey=zone:brake}}") == 2


def test_global_fishing_summary_preserves_reversible_member_and_native_evidence_identities() -> None:
    sources = _global_fishing_sources()
    generator = ItemSectionGenerator()
    manifest = generator.provenance_manifest(sources)
    groups = manifest["fishing_groups"]
    assert len(groups) == 1
    assert groups[0]["chance"] == 1.25
    assert set(groups[0]["member_acquisition_keys"]) == {
        f"acq:water:{water}:{period}" for water in range(31) for period in ("day", "night")
    }
    assert groups[0]["native_pool_acquisition_keys"] == ["acq:global"]
    assert manifest["acquisitions"] == [fact_to_dict(fact) for fact in sources.acquisitions]
    assert not any(key.startswith("acq:brake:") for key in groups[0]["member_acquisition_keys"])


def test_global_fishing_summary_does_not_hide_additional_source_gates() -> None:
    sources = _global_fishing_sources()
    original = sources.acquisitions[0]
    gated = replace(
        original,
        conditions=(*original.conditions, ProvenanceCondition("quest", 0, 0, "quest_done", "quest:unlock")),
    )
    sources.acquisitions = (gated, *sources.acquisitions[1:])
    groups = ItemSectionGenerator()._fishing_summary_groups(sources)
    members = {fact.acquisition_key for facts, _native in groups.values() for fact in facts}
    assert gated.acquisition_key not in members
    assert len(members) == 61


def test_global_fishing_coverage_rejects_a_lost_group_member_identity() -> None:
    sources = _global_fishing_sources()
    generator = ItemSectionGenerator()
    manifest = generator.provenance_manifest(sources)
    manifest["fishing_groups"][0]["member_acquisition_keys"].pop()
    with pytest.raises(ValueError, match="coverage differs for fishing_groups"):
        generator.validate_provenance_manifest(sources, manifest)


def test_article_assembler_rejects_an_entity_without_canonical_lifecycle() -> None:
    generator = EntityPageGenerator.__new__(EntityPageGenerator)
    generator.context = SimpleNamespace(
        item_provenance_repo=SimpleNamespace(get_disposition=lambda _key: None),
    )
    with pytest.raises(ValueError, match="Canonical item disposition is missing: item:missing"):
        generator._assemble_source_info(Item(stable_key="item:missing", item_name="Missing"))


@pytest.mark.parametrize(
    "dimension",
    ["item_stable_key", "disposition", "reason", "evidence", "current_pages", "former_pages"],
)
def test_article_provenance_coverage_rejects_a_lost_lifecycle_dimension(dimension: str) -> None:
    disposition = ItemDisposition(
        "item:map",
        "current",
        reason="Reviewed item identity",
        evidence="lifecycle input",
        current_pages=("Map",),
        former_pages=("Old Map",),
    )
    sources = _global_fishing_sources()
    sources.disposition = disposition
    generator = ItemSectionGenerator()
    manifest = generator.provenance_manifest(sources)
    assert manifest["disposition"] == fact_to_dict(disposition)
    del manifest["disposition"][dimension]
    with pytest.raises(ValueError, match="coverage differs for disposition"):
        generator.validate_provenance_manifest(sources, manifest)


def test_article_provenance_coverage_rejects_a_lost_lifecycle_record() -> None:
    sources = SourceInfo(disposition=ItemDisposition("item:map", "current"))
    generator = ItemSectionGenerator()
    manifest = generator.provenance_manifest(sources)
    manifest["disposition"] = None
    with pytest.raises(ValueError, match="coverage differs for disposition"):
        generator.validate_provenance_manifest(sources, manifest)


@pytest.mark.parametrize("state", ["removed", "unobtainable", "unused"])
def test_reviewed_noncurrent_lifecycle_retains_facts_without_advertising_sources(state: str) -> None:
    sources = _global_fishing_sources()
    sources.disposition = ItemDisposition("item:map", state, evidence="reviewed lifecycle input")
    sources.acquisitions += (_source("acq:vendor", "item:map", "vendor", "character:vendor"),)
    generator = ItemSectionGenerator()
    enriched = EnrichedItemData(
        item=Item(stable_key="item:map", item_name="Map"),
        stats=[],
        classes=[],
        sources=sources,
    )
    assert generator._format_vendor_sources(enriched) == ""
    assert generator._format_fishing(enriched) == ""
    manifest = generator.provenance_manifest(sources)
    assert manifest["disposition"] == fact_to_dict(sources.disposition)
    assert manifest["acquisitions"] == [fact_to_dict(fact) for fact in sources.acquisitions]
    assert manifest["fishing_groups"] == []
    assert all(
        row["field"] is None and "non-current lifecycle" in row["reason"] for row in manifest["presentation"].values()
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("false", "before claiming your Reliquary"), ("true", "after claiming your Reliquary")],
)
def test_account_availability_uses_familiar_state_label_without_exposing_metadata(
    value: str,
    expected: str,
) -> None:
    item = Item(stable_key="item:arbitrary", item_name="Arbitrary")
    location_key = "location:account-gated-vendor"
    condition = ProvenanceCondition(
        "account",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value=value,
        scope=location_key,
        phase="availability",
    )
    fact = replace(
        _source("acq:account", item.stable_key, "vendor", "character:vendor"),
        locations=(
            ProvenanceLocation(
                location_key,
                "interaction",
                zone_stable_key="zone:hall",
                conditions=(condition,),
            ),
        ),
    )
    sources = SourceInfo(
        acquisitions=(fact,),
        links={
            "character:vendor": CharacterLink("Vendor", "Vendor", stable_key="character:vendor"),
            "zone:hall": ZoneLink("Hall", "Hall", stable_key="zone:hall"),
        },
    )
    generator = ItemSectionGenerator()
    text = generator._format_vendor_sources(
        EnrichedItemData(item=item, stats=[], classes=[], sources=sources),
    )
    assert expected in text
    assert "account_state" not in text
    assert location_key not in text
    assert "availability" not in text
    assert generator.provenance_manifest(sources)["acquisitions"] == [fact_to_dict(fact)]


def test_account_outcome_does_not_become_a_contradictory_availability_requirement() -> None:
    item = Item(stable_key="item:arbitrary", item_name="Arbitrary")
    location_key = "location:account-gated-source"
    availability = ProvenanceCondition(
        "account",
        0,
        0,
        "account_state",
        "account_state:reliquary_claimed",
        actor="account",
        value="false",
        scope=location_key,
        phase="availability",
    )
    outcome = replace(availability, atom_index=1, value="true", phase="operation_outcome")
    fact = replace(
        _source("acq:account", item.stable_key, "character_drop", "character:source", 100),
        locations=(
            ProvenanceLocation(
                location_key,
                "spawn",
                zone_stable_key="zone:hall",
                conditions=(availability, outcome),
            ),
        ),
    )
    sources = SourceInfo(acquisitions=(fact,))
    generator = ItemSectionGenerator()
    text = generator._format_drop_sources(
        EnrichedItemData(item=item, stats=[], classes=[], sources=sources),
    )
    assert text.count("before claiming your Reliquary") == 1
    assert "after claiming your Reliquary" not in text
    assert "operation_outcome" not in text
    manifest = generator.provenance_manifest(sources)
    assert manifest["acquisitions"] == [fact_to_dict(fact)]
    conditions = manifest["acquisitions"][0]["locations"][0]["conditions"]
    assert [condition["phase"] for condition in conditions] == ["availability", "operation_outcome"]
    assert [condition["scope"] for condition in conditions] == [location_key, location_key]


def test_blessing_removal_byproduct_is_not_an_ordinary_recipe_and_resolves_its_actual_outcome() -> None:
    shard = Item(stable_key="item:planar_shard", item_name="Planar Shard")
    equipment = Item(stable_key="item:equipment", item_name="Equipment")
    diamond_key = "item:diamond"
    diamond = ItemLink("Diamond", "Diamond", stable_key=diamond_key)
    byproduct = replace(
        _source("acq:blessing_shard", shard.stable_key, "crafting", diamond_key),
        mechanic="remove_blessing",
        variant_key="blessing_removal_byproduct",
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
        probability_kind="not_applicable",
        probability_basis="not_applicable",
        conditions=(
            ProvenanceCondition(
                "equipment_input",
                0,
                0,
                "quality",
                minimum=2,
                maximum=3,
                phase="operation_input",
            ),
        ),
        evidence=(
            ProvenanceEvidence("raw.NativeItemBindings", "GameManager.PlanarShard"),
            ProvenanceEvidence("items", diamond_key),
        ),
    )
    use = ItemUse(
        "use:remove_blessing",
        equipment.stable_key,
        diamond_key,
        "smithing",
        mechanic="remove_blessing",
        outcome_key=byproduct.acquisition_key,
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )

    def acquisitions(key: str) -> list[ItemAcquisition]:
        assert key != diamond_key, "The operation target is not the byproduct's item identity."
        return [byproduct] if key == shard.stable_key else []

    def recipe(key: str) -> CraftingRecipe | None:
        assert key != diamond_key, "Blessing removal must not require an ordinary mold recipe."
        return None

    generator = EntityPageGenerator.__new__(EntityPageGenerator)
    generator.item_generator = ItemSectionGenerator()
    generator.item_provenance_manifest = {}
    generator._item_source_links = {diamond_key: diamond}
    generator.context = SimpleNamespace(
        item_provenance_repo=SimpleNamespace(
            get_disposition=lambda key: ItemDisposition(key, "current"),
            get_acquisitions=acquisitions,
            get_uses=lambda key: [use] if key == equipment.stable_key else [],
            iter_acquisitions=lambda: iter((byproduct,)),
        ),
        item_repo=SimpleNamespace(get_crafting_recipe=recipe),
    )
    shard_sources = generator._assemble_source_info(shard)
    assert shard_sources.recipes == []
    text = generator.item_generator._format_crafting_sources(
        EnrichedItemData(item=shard, stats=[], classes=[], sources=shard_sources),
    )[0]
    assert text == f"From removing a blessing with {diamond}"
    assert generator.item_provenance_manifest[shard.stable_key]["acquisitions"] == [fact_to_dict(byproduct)]

    equipment_sources = generator._assemble_source_info(equipment)
    assert equipment_sources.outcomes[use.outcome_key] is byproduct
    manifest = generator.item_provenance_manifest[equipment.stable_key]
    assert manifest["uses"] == [fact_to_dict(use)]
    assert manifest["outcomes"] == [fact_to_dict(byproduct)]
