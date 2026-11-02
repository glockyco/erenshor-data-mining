from __future__ import annotations

import hashlib
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import FakeItemRepository, make_item, public_source, public_use

from erenshor.application.wiki_lua.items_v2 import (
    build_items_v2_data,
    generate_items_v2_modules,
    item_bucket,
    write_items_v2_modules,
)
from erenshor.application.wiki_lua.lua_writer import module_text
from erenshor.domain.value_objects.item_public_view import (
    ItemStatus,
    MechanismParameter,
    PublicCondition,
    PublicPlace,
    PublicSource,
    PublicUse,
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
        self.status_record = ItemStatus(key, "current", None, former_pages=("Former Sword",))
        self.extra_statuses: list[ItemStatus] = []
        condition = PublicCondition(0, 0, 0, "gate:room", "room_furnished", "item:furniture", reference_slot="1")
        self.source_records = [
            public_source(
                "source:fishing:day",
                key,
                "fishing",
                "water:lake",
                source_copy_stable_key="water:copy",
                variant_key="day:slot:2",
                probability_kind="exact",
                probability_min=0.002,
                probability_max=0.002,
                probability_basis="per_successful_catch",
                quantity_min=2,
                quantity_max=2,
                quantity_kind="exact",
                place_set_key="places:lake",
                conditions=(condition, PublicCondition(1, 0, 0, "gate:time", "time_of_day", value="day")),
            )
        ]
        self.use_records = [public_use("use:quest:slot:3", key, "quest:offering", "quest_requirement", material_slot=3)]
        self.place_records = [
            PublicPlace(
                "places:lake",
                "location:lake",
                "unlocated",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                conditions=(condition,),
            )
        ]
        self.parameter_records: list[MechanismParameter] = []

    def statuses(self) -> list[ItemStatus]:
        return ([] if self.status_record is None else [self.status_record]) + self.extra_statuses

    def sources(self) -> list[PublicSource]:
        return self.source_records

    def uses(self) -> list[PublicUse]:
        return self.use_records

    def places(self, key: str | None) -> tuple[PublicPlace, ...]:
        return tuple(place for place in self.place_records if place.place_set_key == key)

    def parameters(self, key: str | None) -> tuple[MechanismParameter, ...]:
        return tuple(parameter for parameter in self.parameter_records if parameter.mechanic_key == key)


def test_public_schema_hoists_places_and_parameters_without_complete_fact_dimensions() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    public = Provenance(key)
    public.source_records[0] = replace(public.source_records[0], mechanic="fishing")
    public.parameter_records = [
        MechanismParameter("fishing", 0, "formula", "fishing_skill", "catch formula", None, None, "availability")
    ]
    data = build_items_v2_data(repo, public, build=BUILD, native_catalog=CATALOG)
    assert data.index["schemaVersion"] == 2
    assert data.index["provenanceSchemaVersion"] == 2
    owner = data.provenance[item_bucket(key)][key]
    assert owner["places"] == {"places:lake": [asdict(public.place_records[0])]}
    assert owner["sources"] == [asdict(public.source_records[0])]
    assert owner["mechanism_parameters"] == {"fishing": [asdict(public.parameter_records[0])]}
    assert owner["usages"] == [asdict(public.use_records[0])]
    assert owner["status"] == asdict(public.status_record)
    modules = generate_items_v2_modules(repo, public, build=BUILD, native_catalog=CATALOG)
    assert modules[f"ItemProvenanceV2/{item_bucket(key)}.lua"] == module_text(
        {
            "byKey": {
                key: {field: value for field, value in owner.items() if field not in {"places", "mechanism_parameters"}}
            },
            "places": owner["places"],
            "mechanism_parameters": owner["mechanism_parameters"],
        }
    )
    for retired in ("player_access_state", "probability_stage", "count_distribution", "actionable"):
        assert retired not in modules[f"ItemProvenanceV2/{item_bucket(key)}.lua"]


def repository() -> CompleteItems:
    item = make_item().model_copy(update={"item_db_index": 0, "worn_effect_stable_key": "spell:worn"})
    return CompleteItems(items=[item], stats={}, classes={})


def test_versioned_writer_preserves_full_identity_dimensions_and_picture_titles(tmp_path: Path) -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    modules = generate_items_v2_modules(repo, Provenance(key), build=BUILD, native_catalog=CATALOG)
    bucket = item_bucket(key)
    assert set(modules) == {"ItemsV2.lua", f"ItemsV2/{bucket}.lua", f"ItemProvenanceV2/{bucket}.lua"}
    entity = modules[f"ItemsV2/{bucket}.lua"]
    facts = modules[f"ItemProvenanceV2/{bucket}.lua"]
    assert '["itemDbIndex"] = 0' in entity
    assert "Sword of Flames render (female).png" in entity
    assert "Sword of Flames screenshot.png" in entity
    assert "Former Sword" in entity
    assert "wornEffect" in entity and "spell:worn" in entity
    for value in (
        "source:fishing:day",
        "source_copy_stable_key",
        "day:slot:2",
        "room_furnished",
        "time_of_day",
        "0.002",
        "per_successful_catch",
        "location:lake",
        "unlocated",
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
    provenance.source_records.append(
        replace(provenance.source_records[0], source_key="acquisition:fishing:night", variant_key="night:slot:2")
    )
    first = generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)
    provenance.source_records.reverse()
    assert generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG) == first
    assert "acquisition:fishing:night" in first[f"ItemProvenanceV2/{item_bucket(key)}.lua"]
    record = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG).provenance[item_bucket(key)][
        key
    ]
    assert record["sources"] == [
        asdict(value) for value in sorted(provenance.source_records, key=lambda row: row.source_key)
    ]
    assert record["usages"] == [asdict(value) for value in provenance.use_records]
    assert record["status"] == asdict(provenance.status_record)


@pytest.mark.parametrize("defect", ["missing_disposition", "wrong_item", "duplicate", "missing_index", "missing_build"])
def test_incomplete_or_ambiguous_contract_fails_closed(defect: str) -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    build = BUILD
    if defect == "missing_disposition":
        provenance.status_record = None  # type: ignore[assignment]
    elif defect == "wrong_item":
        provenance.source_records[0] = replace(provenance.source_records[0], item_stable_key="item:other")
    elif defect == "duplicate":
        provenance.source_records *= 2
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
    provenance.status_record = replace(provenance.status_record, disposition="removed")
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
    provenance.status_record = replace(provenance.status_record, disposition="current")
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
    outcome = public_source(
        "acquisition:hidden:slot:1",
        "item:hidden",
        "item_drop",
        key,
        probability_kind="exact",
        probability_min=12.5,
        probability_max=12.5,
    )
    provenance.source_records.append(outcome)
    provenance.use_records.append(
        public_use("use:hidden:slot:1", key, "item:hidden", "item_drop", outcome_key=outcome.source_key)
    )
    provenance.extra_statuses.append(ItemStatus("item:hidden", "current", None))
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)
    assert "item:hidden" not in data.index["byKey"]
    assert data.index["outcomeItemByKey"] == {outcome.source_key: "item:hidden"}
    hidden_bucket = data.index["provenanceByKey"]["item:hidden"]
    assert data.provenance[hidden_bucket]["item:hidden"]["sources"] == [asdict(outcome)]
    modules = generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)
    assert f"ItemProvenanceV2/{hidden_bucket}.lua" in modules


def test_versioned_provenance_preserves_probability_ranges_and_all_canonical_use_kinds() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    provenance.source_records = [
        public_source(
            "common-world:range",
            key,
            "common_world_item",
            None,
            probability_kind="bounded",
            probability_min=0.123,
            probability_max=0.987,
        ),
    ]
    provenance.use_records = [
        public_use(
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
    assert record["sources"] == [asdict(provenance.source_records[0])]
    assert record["usages"] == [
        asdict(value) for value in sorted(provenance.use_records, key=lambda value: value.use_key)
    ]


def test_historical_only_dispositions_have_provenance_buckets_without_entity_records() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    historical = ItemStatus(
        "item:historical-only",
        "removed",
        reason="Reviewed removed content",
        former_pages=("Historical Item",),
    )
    provenance.extra_statuses.append(historical)

    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)

    assert historical.item_stable_key not in data.index["byKey"]
    bucket = data.index["provenanceByKey"][historical.item_stable_key]
    assert historical.item_stable_key not in data.items.get(bucket, {})
    assert data.provenance[bucket][historical.item_stable_key] == {
        "sources": [],
        "usages": [],
        "status": asdict(historical),
        "references": {},
        "places": {},
        "mechanism_parameters": {},
    }
    modules = generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)
    assert f"ItemProvenanceV2/{bucket}.lua" in modules
    provenance.extra_statuses.reverse()
    assert generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG) == modules


def test_duplicate_canonical_dispositions_fail_closed() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    provenance.extra_statuses.append(provenance.status_record)
    with pytest.raises(ValueError, match="duplicate canonical disposition"):
        generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)


def test_byproduct_outcome_lookup_uses_actual_acquisition_owner_not_use_target() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    outcome = public_source(
        "acquisition:remove-blessing:shard",
        "item:physical-shard",
        "crafting",
        key,
        mechanic="remove_blessing",
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )
    use = public_use(
        "use:remove-blessing:operation",
        key,
        "item:removal-diamond",
        "smithing",
        mechanic="remove_blessing",
        outcome_key=outcome.source_key,
    )
    provenance.source_records.append(outcome)
    provenance.use_records.append(use)
    provenance.extra_statuses.extend(
        [ItemStatus("item:physical-shard", "current", None), ItemStatus("item:removal-diamond", "current", None)]
    )

    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)

    assert data.index["outcomeItemByKey"] == {outcome.source_key: outcome.item_stable_key}
    owner = data.index["outcomeItemByKey"][use.outcome_key]
    bucket = data.index["provenanceByKey"][owner]
    assert data.provenance[bucket][owner]["sources"] == [asdict(outcome)]
    assert asdict(use) in data.provenance[item_bucket(key)][key]["usages"]
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
    provenance.use_records.append(public_use("use:missing-outcome", key, key, "smithing", outcome_key=outcome_key))
    with pytest.raises(ValueError, match="Missing canonical acquisition outcomes"):
        generate_items_v2_modules(repo, provenance, build=BUILD, native_catalog=CATALOG)


def test_outcome_owner_index_rejects_ambiguous_acquisition_identity() -> None:
    repo = repository()
    key = repo.get_items_for_wiki_generation()[0].stable_key
    provenance = Provenance(key)
    outcome = provenance.source_records[0]
    provenance.source_records.append(replace(outcome, item_stable_key="item:other-owner"))
    provenance.use_records.append(public_use("use:ambiguous", key, key, "smithing", outcome_key=outcome.source_key))
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
        provenance.extra_statuses.append(ItemStatus(key, "current", None))
        provenance.source_records.append(
            replace(provenance.source_records[0], source_key=f"acquisition:{key}", item_stable_key=key)
        )
    return repo, provenance, (first, second)


def test_adaptive_provenance_split_preserves_every_owner_and_fact_once() -> None:
    repo, provenance, owners = split_fixture()
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)
    budget = max(
        len(
            module_text(
                {
                    "byKey": {
                        key: {
                            field: value
                            for field, value in record.items()
                            if field not in {"places", "mechanism_parameters"}
                        }
                    },
                    "places": record["places"],
                    "mechanism_parameters": record["mechanism_parameters"],
                }
            ).encode()
        )
        for records in data.provenance.values()
        for key, record in records.items()
    )
    modules = generate_items_v2_modules(repo, provenance, build=BUILD, max_page_bytes=budget, native_catalog=CATALOG)
    relation_modules = {name: text for name, text in modules.items() if name.startswith("ItemProvenanceV2/")}
    assert f"ItemProvenanceV2/{item_bucket(owners[0])}.lua" not in relation_modules
    for owner in owners:
        shard = hashlib.sha256(owner.encode()).hexdigest()[:3]
        assert owner in relation_modules[f"ItemProvenanceV2/{shard}.lua"]
        assert f'["{owner}"] = "{shard}"' in modules["ItemsV2.lua"]
    for acquisition in provenance.source_records:
        assert (
            sum(text.count(f'["source_key"] = "{acquisition.source_key}"') for text in relation_modules.values()) == 1
        )
    for disposition in provenance.statuses():
        assert sum(text.count(f'["{disposition.item_stable_key}"] = {{') for text in relation_modules.values()) == 1
    assert all(len(text.encode()) <= budget for text in relation_modules.values())
    provenance.source_records.reverse()
    provenance.extra_statuses.reverse()
    assert (
        generate_items_v2_modules(repo, provenance, build=BUILD, max_page_bytes=budget, native_catalog=CATALOG)
        == modules
    )


def test_single_owner_overflow_fails_without_omitting_facts() -> None:
    repo = repository()
    provenance = Provenance(repo.get_items_for_wiki_generation()[0].stable_key)
    with pytest.raises(ValueError, match="owner cannot fit page budget"):
        generate_items_v2_modules(repo, provenance, build=BUILD, max_page_bytes=10, native_catalog=CATALOG)


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
    condition = PublicCondition(0, 0, 0, "gate:quest", "quest_done", quest)
    location = PublicPlace(
        "places:raider",
        "location:raider",
        "fixed",
        None,
        "zone:elderstone",
        None,
        None,
        None,
        None,
        None,
        None,
        copy,
        conditions=(PublicCondition(0, 0, 0, "gate:local", "quest_not_done", other_quest),),
    )
    provenance.place_records = [location]
    provenance.source_records = [
        public_source(
            "acquisition:raider",
            key,
            "character_drop",
            copy,
            source_copy_stable_key=copy,
            conditions=(condition,),
            place_set_key="places:raider",
        )
    ]
    provenance.use_records = [
        public_use(
            "use:quest",
            key,
            other_quest,
            "quest_requirement",
            place_set_key="places:raider",
            conditions=(condition,),
        )
    ]
    data = build_items_v2_data(repo, provenance, build=BUILD, native_catalog=catalog)
    record = data.provenance[item_bucket(key)][key]
    assert record["sources"] == [asdict(provenance.source_records[0])]
    assert record["usages"] == [asdict(provenance.use_records[0])]
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
    acquisition = provenance.source_records[0]
    if path == "source":
        acquisition = replace(acquisition, source_stable_key=unknown)
    elif path == "copy":
        acquisition = replace(acquisition, source_copy_stable_key=unknown)
    elif path == "target":
        provenance.use_records[0] = replace(provenance.use_records[0], target_stable_key=unknown)
    elif path == "condition":
        acquisition = replace(acquisition, conditions=(PublicCondition(0, 0, 0, "gate", "quest_done", unknown),))
    elif path == "location":
        provenance.place_records[0] = replace(provenance.place_records[0], source_copy_stable_key=unknown)
    elif path == "local_condition":
        provenance.place_records[0] = replace(
            provenance.place_records[0],
            conditions=(PublicCondition(0, 0, 0, "gate", "quest_done", unknown),),
        )
    else:
        item.complete_on_read_stable_key = unknown
    provenance.source_records[0] = acquisition
    with pytest.raises(ValueError, match="unknown native quest"):
        build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG)


def test_native_reference_names_and_pages_must_be_real_catalog_values() -> None:
    repo = repository()
    provenance = Provenance(repo.get_items_for_wiki_generation()[0].stable_key)
    for malformed in ({"name": None}, {"name": ""}, {"name": "An Offering", "page": ""}):
        with pytest.raises(ValueError, match="native reference"):
            build_items_v2_data(repo, provenance, build=BUILD, native_catalog=CATALOG | {"quest:offering": malformed})
