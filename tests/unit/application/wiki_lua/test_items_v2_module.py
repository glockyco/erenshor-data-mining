from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import FakeItemRepository, make_item

from erenshor.application.wiki_lua.items_v2 import (
    build_items_v2_data,
    generate_items_v2_modules,
    item_bucket,
    write_items_v2_modules,
)
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.application.wiki_lua.validation import LuaValidationResult
from erenshor.domain.value_objects.item_provenance import (
    ItemAcquisition,
    ItemDisposition,
    ItemUse,
    ProvenanceCondition,
    ProvenanceEvidence,
    ProvenanceLocation,
    fact_to_dict,
)
from erenshor.infrastructure.content_lifecycle import ContentLifecycle, LifecyclePage

BUILD = {"gameBuildId": "test-build", "publishedAt": "2026-10-17T00:00:00Z"}
CATALOG = {
    "item:furniture": {"name": "Reliquary Furniture"},
    "quest:offering": {"name": "An Offering"},
    "item:hidden": {"name": "Hidden Reward"},
    "item:target": {"name": "Crafted Target", "page": "Crafted Target"},
    "item:sword_of_flames": {"name": "Sword of Flames", "page": "Sword of Flames"},
    "item:physical-shard": {"name": "Physical Shard"},
    "item:removal-diamond": {"name": "Removal Diamond"},
}


class CompleteItems(FakeItemRepository):
    def get_item_renders(self, stable_key: str) -> dict[str | None, str]:
        return {"male": "Sword of Flames render (male).png", "female": "Sword of Flames render (female).png"}


class Provenance:
    def __init__(self, key: str) -> None:
        self.disposition = ItemDisposition(key, "current", former_pages=("Former Sword",))
        self.extra_dispositions: list[ItemDisposition] = []
        condition = ProvenanceCondition("gate:room", 0, 0, "room_furnished", "item:furniture", reference_slot="1")
        self.acquisitions = [
            ItemAcquisition(
                "acquisition:fishing:day",
                key,
                "fishing",
                "water:lake",
                source_copy_stable_key="water:copy",
                variant_key="day:slot:2",
                probability_kind="exact",
                probability_min=0.002,
                probability_max=0.002,
                probability_basis="per_successful_catch",
                probability_stage="final_acquisition",
                quantity_min=2,
                quantity_max=2,
                quantity_kind="exact",
                conditions=(condition, ProvenanceCondition("gate:time", 0, 0, "time_of_day", value="day")),
                locations=(ProvenanceLocation("location:lake", "unlocated", conditions=(condition,)),),
                evidence=(ProvenanceEvidence("water_fishables", "lake|day|2"),),
            )
        ]
        self.uses = [ItemUse("use:quest:slot:3", key, "quest:offering", "quest_requirement", material_slot=3)]

    def iter_dispositions(self) -> list[ItemDisposition]:
        return ([] if self.disposition is None else [self.disposition]) + self.extra_dispositions

    def iter_acquisitions(self) -> list[ItemAcquisition]:
        return self.acquisitions

    def iter_uses(self) -> list[ItemUse]:
        return self.uses


def repository() -> CompleteItems:
    item = make_item().model_copy(update={"item_db_index": 0, "worn_effect_stable_key": "spell:worn"})
    return CompleteItems(items=[item], stats={}, classes={})


def test_versioned_writer_preserves_full_identity_dimensions_and_picture_titles(tmp_path: Path) -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    modules = generate_items_v2_modules(repo, Provenance(key), build=BUILD, native_catalog=CATALOG)
    bucket = item_bucket(key)
    assert set(modules) == {"ItemsV2.lua", f"ItemsV2/{bucket}.lua", f"ItemProvenanceV1/{bucket}.lua"}
    entity = modules[f"ItemsV2/{bucket}.lua"]
    facts = modules[f"ItemProvenanceV1/{bucket}.lua"]
    assert '["itemDbIndex"] = 0' in entity
    assert "Sword of Flames render (female).png" in entity
    assert "Sword of Flames screenshot.png" in entity
    assert "Former Sword" in entity
    assert "wornEffect" in entity and "spell:worn" in entity
    for value in (
        "acquisition:fishing:day",
        "source_copy_stable_key",
        "day:slot:2",
        "room_furnished",
        "time_of_day",
        "0.002",
        "final_acquisition",
        "per_successful_catch",
        "location:lake",
        "unlocated",
        "water_fishables",
        "lake|day|2",
        "use:quest:slot:3",
        "material_slot",
    ):
        assert value in facts
    assert "obtainedFrom" not in entity
    paths = write_items_v2_modules(
        repo,
        Provenance(key),
        tmp_path,
        build=BUILD,
        max_page_bytes=3_145_728,
        validate=lambda path: LuaValidationResult(path, "test"),
        native_catalog=CATALOG,
    )
    assert {path.relative_to(tmp_path / "Erenshor" / "Data").as_posix() for path in paths} == set(modules)
    assert all(
        path.read_text() == modules[path.relative_to(tmp_path / "Erenshor" / "Data").as_posix()] for path in paths
    )


def test_serialization_is_deterministic_without_collapsing_equal_fact_values() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    provenance.acquisitions.append(
        replace(provenance.acquisitions[0], acquisition_key="acquisition:fishing:night", variant_key="night:slot:2")
    )
    first = generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)
    provenance.acquisitions.reverse()
    assert generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG) == first
    assert "acquisition:fishing:night" in first[f"ItemProvenanceV1/{item_bucket(key)}.lua"]
    record = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG).provenance[item_bucket(key)][
        key
    ]
    assert record["acquisitions"] == [
        fact_to_dict(value) for value in sorted(provenance.acquisitions, key=lambda row: row.acquisition_key)
    ]
    assert record["uses"] == [fact_to_dict(value) for value in provenance.uses]
    assert record["disposition"] == fact_to_dict(provenance.disposition)


@pytest.mark.parametrize("defect", ["missing_disposition", "wrong_item", "duplicate", "missing_index", "missing_build"])
def test_incomplete_or_ambiguous_contract_fails_closed(defect: str) -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    build = BUILD
    if defect == "missing_disposition":
        provenance.disposition = None  # type: ignore[assignment]
    elif defect == "wrong_item":
        provenance.acquisitions[0] = replace(provenance.acquisitions[0], item_stable_key="item:other")
    elif defect == "duplicate":
        provenance.acquisitions *= 2
    elif defect == "missing_index":
        repo.get_items_for_wiki_generation()[0].item_db_index = None
    elif defect == "missing_build":
        build = {}
    with pytest.raises(ValueError):
        generate_items_v2_modules(repo, provenance, build=build, native_catalog=CATALOG)


def test_reviewed_notice_enriches_but_cannot_override_canonical_lifecycle() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    provenance.disposition = replace(provenance.disposition, disposition="removed")
    page = LifecyclePage(
        title="Sword of Flames",
        stable_key=key,
        state="removed",
        thing="item",
        update="The Update",
        date="2026-10-01",
        patch_notes_url="https://example.com/patch",
        source="Reviewed shipped item identity",
    )
    lifecycle = ContentLifecycle({"Sword of Flames": page}, {}, {})
    row = build_items_v2_data(repo, provenance, build=BUILD, lifecycle=lifecycle, native_catalog=CATALOG).items[
        item_bucket(key)
    ][key]
    assert row["lifecycle"]["notice"] == {
        "update": "The Update",
        "date": "2026-10-01",
        "url": "https://example.com/patch",
    }
    provenance.disposition = replace(provenance.disposition, disposition="current")
    with pytest.raises(ValueError, match="disagrees with canonical"):
        build_items_v2_data(repo, provenance, build=BUILD, lifecycle=lifecycle, native_catalog=CATALOG)


def test_every_effect_survives_without_inventing_an_attack_trigger_for_other_slots() -> None:
    repo = repository()
    item = repo.get_items_for_wiki_generation()[0]
    item.required_slot = "Ring"
    item.weapon_proc_on_hit_stable_key = "spell:proc"
    item.weapon_proc_chance = 0.0
    item.item_effect_on_click_stable_key = "spell:click"
    item.item_skill_use_stable_key = "skill:use"
    item.teach_spell_stable_key = "spell:learn"
    item.teach_skill_stable_key = "skill:learn"
    item.aura_stable_key = "spell:aura"
    key = item.stable_key
    row = build_items_v2_data(repo, Provenance(key), build=BUILD, native_catalog=CATALOG).items[item_bucket(key)][key]
    effects = {effect["kind"]: effect for effect in row["effects"]}
    assert set(effects) == {
        "weaponProc",
        "clickEffect",
        "skillUse",
        "teachesSpell",
        "teachesSkill",
        "aura",
        "wornEffect",
    }
    assert effects["weaponProc"] == {"kind": "weaponProc", "spellKey": "spell:proc", "chance": 0.0}
    assert effects["skillUse"]["skillKey"] == "skill:use"


def test_hidden_container_rewards_keep_exact_outcome_lookup_without_article_records() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    outcome = ItemAcquisition(
        "acquisition:hidden:slot:1",
        "item:hidden",
        "item_drop",
        key,
        probability_kind="exact",
        probability_min=12.5,
        probability_max=12.5,
        guarantee_scope="pool",
        guaranteed_roll_count=1,
    )
    provenance.acquisitions.append(outcome)
    provenance.uses.append(
        ItemUse("use:hidden:slot:1", key, "item:hidden", "item_drop", outcome_key=outcome.acquisition_key)
    )
    provenance.extra_dispositions.append(ItemDisposition("item:hidden", "current"))
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)
    assert "item:hidden" not in data.index["byKey"]
    assert data.index["outcomeItemByKey"] == {outcome.acquisition_key: "item:hidden"}
    hidden_bucket = data.index["provenanceByKey"]["item:hidden"]
    assert data.provenance[hidden_bucket]["item:hidden"]["acquisitions"] == [fact_to_dict(outcome)]
    modules = generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)
    assert f"ItemProvenanceV1/{hidden_bucket}.lua" in modules


def test_versioned_provenance_preserves_probability_ranges_and_all_canonical_use_kinds() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    provenance.acquisitions = [
        ItemAcquisition(
            "common-world:range",
            key,
            "common_world_item",
            None,
            probability_kind="bounded",
            probability_min=0.123,
            probability_max=0.987,
        ),
    ]
    provenance.uses = [
        ItemUse(
            f"use:{kind}:{slot}",
            key,
            "item:target",
            kind,
            material_slot=slot,
            quantity_min=2,
            quantity_max=2,
            quantity_kind="exact",
            mechanic=mechanic,
        )
        for slot, (kind, mechanic) in enumerate(
            (
                ("crafting_material", None),
                ("quest_requirement", None),
                ("smithing", "upgrade_material"),
                ("smithing", "blessing_removal_material"),
            ),
            start=1,
        )
    ]
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)
    record = data.provenance[item_bucket(key)][key]
    assert record["acquisitions"] == [fact_to_dict(provenance.acquisitions[0])]
    assert record["uses"] == [fact_to_dict(value) for value in sorted(provenance.uses, key=lambda value: value.use_key)]


def test_historical_only_dispositions_have_provenance_buckets_without_entity_records() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    historical = ItemDisposition(
        "item:historical-only",
        "removed",
        reason="Reviewed removed content",
        former_pages=("Historical Item",),
    )
    provenance.extra_dispositions.append(historical)

    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)

    assert historical.item_stable_key not in data.index["byKey"]
    bucket = data.index["provenanceByKey"][historical.item_stable_key]
    assert historical.item_stable_key not in data.items.get(bucket, {})
    assert data.provenance[bucket][historical.item_stable_key] == {
        "acquisitions": [],
        "uses": [],
        "disposition": fact_to_dict(historical),
        "references": {},
    }
    modules = generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)
    assert f"ItemProvenanceV1/{bucket}.lua" in modules
    provenance.extra_dispositions.reverse()
    assert generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG) == modules


def test_duplicate_canonical_dispositions_fail_closed() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    provenance.extra_dispositions.append(provenance.disposition)
    with pytest.raises(ValueError, match="duplicate canonical disposition"):
        generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)


def test_byproduct_outcome_lookup_uses_actual_acquisition_owner_not_use_target() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    outcome = ItemAcquisition(
        "acquisition:remove-blessing:shard",
        "item:physical-shard",
        "crafting",
        key,
        mechanic="remove_blessing",
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )
    use = ItemUse(
        "use:remove-blessing:operation",
        key,
        "item:removal-diamond",
        "smithing",
        mechanic="remove_blessing",
        outcome_key=outcome.acquisition_key,
    )
    provenance.acquisitions.append(outcome)
    provenance.uses.append(use)
    provenance.extra_dispositions.extend(
        [ItemDisposition("item:physical-shard", "current"), ItemDisposition("item:removal-diamond", "current")]
    )

    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)

    assert data.index["outcomeItemByKey"] == {outcome.acquisition_key: outcome.item_stable_key}
    owner = data.index["outcomeItemByKey"][use.outcome_key]
    bucket = data.index["provenanceByKey"][owner]
    assert data.provenance[bucket][owner]["acquisitions"] == [fact_to_dict(outcome)]
    assert fact_to_dict(use) in data.provenance[item_bucket(key)][key]["uses"]
    assert owner != use.target_stable_key
    assert owner not in data.index["byKey"]
    assert data.provenance[bucket][owner]["references"] == {
        "item:physical-shard": {"key": "item:physical-shard", "name": "Physical Shard"},
        key: {"key": key, "name": "Sword of Flames", "page": "Sword of Flames"},
    }
    assert "item:physical-shard" not in data.provenance[item_bucket(key)][key]["references"]


@pytest.mark.parametrize("outcome_key", ["acquisition:missing", "use:quest:slot:3"])
def test_outcome_owner_index_rejects_unknown_or_nonacquisition_references(outcome_key: str) -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    provenance.uses.append(ItemUse("use:missing-outcome", key, key, "smithing", outcome_key=outcome_key))
    with pytest.raises(ValueError, match="Missing canonical acquisition outcomes"):
        generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)


def test_outcome_owner_index_rejects_ambiguous_acquisition_identity() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    outcome = provenance.acquisitions[0]
    provenance.acquisitions.append(replace(outcome, item_stable_key="item:other-owner"))
    provenance.uses.append(ItemUse("use:ambiguous", key, key, "smithing", outcome_key=outcome.acquisition_key))
    with pytest.raises(ValueError, match="duplicate canonical fact identity"):
        generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)


def split_fixture() -> tuple[CompleteItems, Provenance, tuple[str, str]]:
    repo = repository()
    provenance = Provenance(repo.get_items_for_wiki_generation()[0].stable_key)
    first = "item:split:0"
    for number in range(1, 10_000):
        second = f"item:split:{number}"
        if item_bucket(first) == item_bucket(second) and (
            hashlib.sha256(first.encode()).hexdigest()[2] != hashlib.sha256(second.encode()).hexdigest()[2]
        ):
            break
    else:
        raise AssertionError("No split fixture collision")
    for key in (first, second):
        provenance.extra_dispositions.append(ItemDisposition(key, "current"))
        provenance.acquisitions.append(
            replace(provenance.acquisitions[0], acquisition_key=f"acquisition:{key}", item_stable_key=key)
        )
    return repo, provenance, (first, second)


def test_adaptive_provenance_split_preserves_every_owner_and_fact_once() -> None:
    repo, provenance, owners = split_fixture()
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)
    budget = max(
        len(module_text({key: record}).encode())
        for records in data.provenance.values()
        for key, record in records.items()
    )
    modules = generate_items_v2_modules(repo, provenance, build=BUILD, max_page_bytes=budget, native_catalog=CATALOG)
    relation_modules = {name: text for name, text in modules.items() if name.startswith("ItemProvenanceV1/")}
    assert f"ItemProvenanceV1/{item_bucket(owners[0])}.lua" not in relation_modules
    for owner in owners:
        shard = hashlib.sha256(owner.encode()).hexdigest()[:3]
        assert owner in relation_modules[f"ItemProvenanceV1/{shard}.lua"]
        assert f'["{owner}"] = "{shard}"' in modules["ItemsV2.lua"]
    for acquisition in provenance.acquisitions:
        assert (
            sum(
                text.count(f'["acquisition_key"] = "{acquisition.acquisition_key}"')
                for text in relation_modules.values()
            )
            == 1
        )
    for disposition in provenance.iter_dispositions():
        assert sum(text.count(f'["{disposition.item_stable_key}"] = {{') for text in relation_modules.values()) == 1
    assert all(len(text.encode()) <= budget for text in relation_modules.values())
    provenance.acquisitions.reverse()
    provenance.extra_dispositions.reverse()
    assert (
        generate_items_v2_modules(repo, provenance, build=BUILD, max_page_bytes=budget, native_catalog=CATALOG)
        == modules
    )


def test_single_owner_overflow_fails_without_omitting_facts() -> None:
    repo = repository()
    provenance = Provenance(repo.get_items_for_wiki_generation()[0].stable_key)
    with pytest.raises(ValueError, match="owner cannot fit page budget"):
        generate_items_v2_modules(repo, provenance, build=BUILD, max_page_bytes=10, native_catalog=CATALOG)


def test_writer_sizes_final_validated_bytes_and_preserves_fitting_bucket(tmp_path: Path) -> None:
    repo, provenance, owners = split_fixture()
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)
    raw = module_text(data.provenance[item_bucket(owners[0])])

    def compact(text: str) -> str:
        return "\n".join(line.lstrip() for line in text.splitlines()) + "\n"

    budget = len(compact(raw).encode())
    assert len(raw.encode()) > budget

    def validate(path: Path) -> LuaValidationResult:
        path.write_text(compact(path.read_text()))
        return LuaValidationResult(path, "test-formatter")

    paths = write_items_v2_modules(
        repo, provenance, tmp_path, build=BUILD, max_page_bytes=budget, validate=validate, native_catalog=CATALOG
    )
    relations = [path for path in paths if path.parent.name == "ItemProvenanceV1"]
    assert len(relations) == 2
    assert next(path for path in relations if path.stem == item_bucket(owners[0])).read_text() == compact(raw)
    assert all(path.stat().st_size <= budget for path in relations)


def test_native_references_cover_sources_targets_conditions_and_locations_without_rewriting_keys() -> None:
    repo = repository()
    item = repo.get_items_for_wiki_generation()[0]
    key = item.stable_key
    copy = "character:a highwayman raider (1):elderstone:-732.18:-51.70:194.52"
    quest = "quest:amethikeys"
    other_quest = "quest:clearingthebonepits"
    catalog = CATALOG | {
        copy: {"name": "A Highwayman Raider", "page": None},
        quest: {"name": "A Retired Locksmith", "page": None},
        other_quest: {"name": "Clearing the Bonepits", "page": None},
        "zone:elderstone": {"name": "Elderstone", "page": "Elderstone"},
    }
    item.assign_quest_on_read_stable_key = quest
    provenance = Provenance(key)
    condition = ProvenanceCondition("gate:quest", 0, 0, "quest_done", quest)
    location = ProvenanceLocation(
        "location:raider",
        "fixed",
        zone_stable_key="zone:elderstone",
        source_copy_stable_key=copy,
        conditions=(ProvenanceCondition("gate:local", 0, 0, "quest_not_done", other_quest),),
    )
    provenance.acquisitions = [
        ItemAcquisition(
            "acquisition:raider",
            key,
            "character_drop",
            copy,
            source_copy_stable_key=copy,
            conditions=(condition,),
            locations=(location,),
        )
    ]
    provenance.uses = [
        ItemUse("use:quest", key, other_quest, "quest_requirement", conditions=(condition,), locations=(location,))
    ]
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=catalog)
    record = data.provenance[item_bucket(key)][key]
    assert record["acquisitions"] == [fact_to_dict(provenance.acquisitions[0])]
    assert record["uses"] == [fact_to_dict(provenance.uses[0])]
    assert record["references"] == {
        copy: {"key": copy, "name": "A Highwayman Raider"},
        quest: {"key": quest, "name": "A Retired Locksmith"},
        other_quest: {"key": other_quest, "name": "Clearing the Bonepits"},
        "zone:elderstone": {"key": "zone:elderstone", "name": "Elderstone", "page": "Elderstone"},
    }


@pytest.mark.parametrize("path", ["source", "copy", "target", "condition", "location", "local_condition", "read"])
def test_unknown_native_references_fail_closed_at_every_item_path(path: str) -> None:
    repo = repository()
    item = repo.get_items_for_wiki_generation()[0]
    provenance = Provenance(item.stable_key)
    unknown = "quest:unknown"
    acquisition = provenance.acquisitions[0]
    if path == "source":
        acquisition = replace(acquisition, source_stable_key=unknown)
    elif path == "copy":
        acquisition = replace(acquisition, source_copy_stable_key=unknown)
    elif path == "target":
        provenance.uses[0] = replace(provenance.uses[0], target_stable_key=unknown)
    elif path == "condition":
        acquisition = replace(acquisition, conditions=(ProvenanceCondition("gate", 0, 0, "quest_done", unknown),))
    elif path == "location":
        acquisition = replace(
            acquisition, locations=(ProvenanceLocation("location", "fixed", source_copy_stable_key=unknown),)
        )
    elif path == "local_condition":
        acquisition = replace(
            acquisition,
            locations=(
                ProvenanceLocation(
                    "location", "fixed", conditions=(ProvenanceCondition("gate", 0, 0, "quest_done", unknown),)
                ),
            ),
        )
    else:
        item.complete_on_read_stable_key = unknown
    provenance.acquisitions[0] = acquisition
    with pytest.raises(ValueError, match="unknown native quest"):
        build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)


def test_native_reference_names_and_pages_must_be_real_catalog_values() -> None:
    repo = repository()
    provenance = Provenance(repo.get_items_for_wiki_generation()[0].stable_key)
    for malformed in ({"name": None}, {"name": ""}, {"name": "An Offering", "page": ""}):
        with pytest.raises(ValueError, match="native reference"):
            build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG | {"quest:offering": malformed})
