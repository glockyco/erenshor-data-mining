from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.unit.application.wiki_lua.fakes import (
    FakeCharacterRepository,
    FakeClassDisplayService,
    FakeFactionRepository,
    FakeItemProvenanceRepository,
    FakeItemRepository,
    FakeProgressionRepository,
    FakeQuestRepository,
    FakeSkillRepository,
    FakeSpellRepository,
    FakeStanceRepository,
    FakeZoneRepository,
    make_character,
    make_item,
    make_quest,
    make_skill,
    make_spell,
    make_stance,
    make_zone,
)

from erenshor.application.wiki_lua.generation import (
    LuaDataModuleGenerationResult,
    build_character_generation_records,
    generate_lua_data_modules,
)
from erenshor.application.wiki_lua.validation import LuaValidationResult
from erenshor.domain.value_objects.item_provenance import ItemAcquisition, ItemDisposition, ItemUse, fact_to_dict
from erenshor.domain.value_objects.progression import ProgressionNode, ProgressionWay
from erenshor.domain.value_objects.treasure import ChestWave, GuardianScaling, TreasureGuardian
from erenshor.infrastructure.content_lifecycle import ContentLifecycle, LifecyclePage, load_content_lifecycle


class FakeBuildRepository:
    def get_build_metadata(self) -> tuple[str, str]:
        return "24405256", "2026-07-27T12:34:56+00:00"


class FakeTreasureRepository:
    def get_treasure_guardians(self) -> list[TreasureGuardian]:
        return [TreasureGuardian("character:ancient horror", "Ancient Horror", "Ancient Horror")]

    def get_guardian_scaling(self) -> list[GuardianScaling]:
        return [GuardianScaling("character:ancient horror", 1, 2, 4, 858, 858, 3, 3, 147, 147, 30, 60, 2, 4)]

    def get_chest_waves(self) -> list[ChestWave]:
        return [ChestWave(0, 0.0, 3, 4, 5.0), ChestWave(1, 1.0, None, None, None)]


def test_generation_validates_nonnull_blank_item_catalog_pages(tmp_path: Path) -> None:
    item = make_item()
    malformed_catalog_item = make_item(stable_key="item:malformed", wiki_page_name="")
    item_repo = FakeItemRepository(
        items=[item],
        catalog_items=[item, malformed_catalog_item],
        stats={},
        classes={},
    )

    with pytest.raises(ValueError, match="Blank link catalog page"):
        generate_lua_data_modules(
            build_repo=FakeBuildRepository(),
            progression_repo=FakeProgressionRepository((), {}),
            treasure_repo=FakeTreasureRepository(),
            item_repo=item_repo,
            provenance_repo=FakeItemProvenanceRepository([item.stable_key]),
            character_repo=FakeCharacterRepository([make_character()]),
            spell_repo=FakeSpellRepository([make_spell()]),
            skill_repo=FakeSkillRepository([make_skill()]),
            stance_repo=FakeStanceRepository([make_stance()]),
            quest_repo=FakeQuestRepository([make_quest()]),
            zone_repo=FakeZoneRepository([make_zone()], {}),
            faction_repo=FakeFactionRepository(),
            class_display=FakeClassDisplayService(),
            output_root=tmp_path,
            max_page_bytes=4194304,
            lifecycle=ContentLifecycle({}, {}, {}),
            validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
        )


def test_generation_wires_canonical_provenance_and_persists_offline_coverage(tmp_path: Path) -> None:
    item = make_item()
    acquisition = ItemAcquisition(
        "world:slot:3",
        item.stable_key,
        "special_world_drop",
        None,
        variant_key="slot:3",
        probability_kind="exact",
        probability_min=0.05,
        probability_max=0.05,
        probability_stage="final_acquisition",
    )
    use = ItemUse("use:quest:2", item.stable_key, "quest:magical_sword", "quest_requirement", material_slot=2)
    provenance = FakeItemProvenanceRepository([item.stable_key], acquisitions=[acquisition], uses=[use])

    result = generate_lua_data_modules(
        build_repo=FakeBuildRepository(),
        progression_repo=FakeProgressionRepository((), {}),
        treasure_repo=FakeTreasureRepository(),
        item_repo=FakeItemRepository(items=[item], stats={}, classes={}),
        provenance_repo=provenance,
        character_repo=FakeCharacterRepository([make_character()]),
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=FakeStanceRepository([make_stance()]),
        quest_repo=FakeQuestRepository([make_quest()]),
        zone_repo=FakeZoneRepository([make_zone()], {}),
        faction_repo=FakeFactionRepository(),
        class_display=FakeClassDisplayService(),
        max_page_bytes=4194304,
        output_root=tmp_path,
        lifecycle=ContentLifecycle({}, {}, {}),
        validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
    )

    from erenshor.application.wiki_lua.items_v2 import item_bucket

    data_dir = tmp_path / "Erenshor" / "Data"
    item_shard_text = (data_dir / "Items" / "Weapons.lua").read_text(encoding="utf-8")
    assert '["obtainedFrom"]' not in item_shard_text
    assert '["usedIn"]' not in item_shard_text
    canonical = (data_dir / "ItemProvenanceV1" / f"{item_bucket(item.stable_key)}.lua").read_text(encoding="utf-8")
    assert acquisition.acquisition_key in canonical
    assert use.use_key in canonical
    assert '["material_slot"] = 2' in canonical
    manifest = json.loads(result.manifest_paths[0].read_text(encoding="utf-8"))
    assert manifest["acquisitions"][0]["fact"] == json.loads(json.dumps(fact_to_dict(acquisition)))


def _run_generation(
    tmp_path: Path,
    *,
    max_page_bytes: int = 4194304,
    item_key: str = "item:sword_of_flames",
    provenance_repo: FakeItemProvenanceRepository | None = None,
    lifecycle: ContentLifecycle | None = None,
    stance_repo: FakeStanceRepository | None = None,
    character_repo: FakeCharacterRepository | None = None,
    progression_repo: FakeProgressionRepository | None = None,
) -> LuaDataModuleGenerationResult:
    item_repo = FakeItemRepository(items=[make_item(stable_key=item_key)], stats={}, classes={})
    return generate_lua_data_modules(
        build_repo=FakeBuildRepository(),
        progression_repo=progression_repo or FakeProgressionRepository((), {}),
        treasure_repo=FakeTreasureRepository(),
        item_repo=item_repo,
        provenance_repo=provenance_repo or FakeItemProvenanceRepository([item_key]),
        character_repo=character_repo or FakeCharacterRepository([make_character()]),
        spell_repo=FakeSpellRepository([make_spell()]),
        skill_repo=FakeSkillRepository([make_skill()]),
        stance_repo=stance_repo or FakeStanceRepository([make_stance()]),
        quest_repo=FakeQuestRepository([make_quest()]),
        zone_repo=FakeZoneRepository([make_zone()], {}),
        faction_repo=FakeFactionRepository(),
        class_display=FakeClassDisplayService(),
        output_root=tmp_path,
        max_page_bytes=max_page_bytes,
        lifecycle=lifecycle if lifecycle is not None else ContentLifecycle({}, {}, {}),
        validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
    )


def test_generation_writes_and_validates_persisted_progression_rows(tmp_path: Path) -> None:
    key = "item:sword_of_flames"
    graph = FakeProgressionRepository(
        (ProgressionNode(key, "item", "Sword", True, 1, "available"),),
        {key: (ProgressionWay("available", ()),)},
    )
    result = _run_generation(tmp_path, progression_repo=graph)
    path = tmp_path / "Erenshor" / "Data" / "Progression.lua"
    assert path in result.written_paths
    assert path in result.validation_tools
    content = path.read_text()
    assert key in content
    assert '["milestone"] = true' in content
    assert '["first"] = true' in content


def test_invalid_progression_does_not_replace_previous_modules(tmp_path: Path) -> None:
    key = "item:unknown"
    graph = FakeProgressionRepository(
        (ProgressionNode(key, "item", "Unknown", True, 1, "available"),),
        {key: (ProgressionWay("available", ()),)},
    )
    previous = tmp_path / "Erenshor" / "Data" / "Progression.lua"
    previous.parent.mkdir(parents=True)
    previous.write_text("previous")
    with pytest.raises(ValueError, match="unknown native identity"):
        _run_generation(tmp_path, progression_repo=graph)
    assert previous.read_text() == "previous"


def test_generated_modules_are_byte_for_byte_deterministic(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first_result = _run_generation(first_root)
    second_result = _run_generation(second_root)

    first_modules = {path.relative_to(first_root): path.read_bytes() for path in first_result.written_paths}
    second_modules = {path.relative_to(second_root): path.read_bytes() for path in second_result.written_paths}
    assert first_modules == second_modules


def test_generation_rejects_oversize_module_without_changing_output(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    item_key = "item:épée"
    _run_generation(reference_root, item_key=item_key, character_repo=FakeCharacterRepository([]))
    module = reference_root / "Erenshor" / "Data" / "Items.lua"
    size = module.stat().st_size
    character_limit = len(module.read_text(encoding="utf-8"))
    assert size > character_limit
    output_root = tmp_path / "output"
    data_dir = output_root / "Erenshor" / "Data"
    data_dir.mkdir(parents=True)
    existing_module = data_dir / "Items.lua"
    existing_module.write_text("return { old = true }\n", encoding="utf-8")
    previous_manifest = output_root / "world-drops-provenance.json"
    previous_manifest.write_text('{"previous": true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match=rf"owner cannot fit page budget.*item:épée.*limit {character_limit * 3 // 4}"):
        _run_generation(
            output_root,
            max_page_bytes=character_limit,
            item_key=item_key,
            character_repo=FakeCharacterRepository([]),
        )

    assert existing_module.read_text(encoding="utf-8") == "return { old = true }\n"
    assert list(data_dir.rglob("*.lua")) == [existing_module]
    assert previous_manifest.read_text(encoding="utf-8") == '{"previous": true}\n'


def test_generation_requires_faction_and_class_dependencies(tmp_path: Path) -> None:
    with pytest.raises(TypeError) as error:
        generate_lua_data_modules(
            build_repo=FakeBuildRepository(),
            progression_repo=FakeProgressionRepository((), {}),
            treasure_repo=FakeTreasureRepository(),
            item_repo=FakeItemRepository(items=[make_item()], stats={}, classes={}),
            provenance_repo=FakeItemProvenanceRepository([make_item().stable_key]),
            character_repo=FakeCharacterRepository([make_character()]),
            spell_repo=FakeSpellRepository([make_spell()]),
            skill_repo=FakeSkillRepository([make_skill()]),
            stance_repo=FakeStanceRepository([make_stance()]),
            quest_repo=FakeQuestRepository([make_quest()]),
            zone_repo=FakeZoneRepository([make_zone()], {}),
            output_root=tmp_path,
            max_page_bytes=4194304,
            lifecycle=ContentLifecycle({}, {}, {}),
            validate=lambda path: LuaValidationResult(path=path, tool="stylua"),
        )

    assert "faction_repo" in str(error.value)
    assert "class_display" in str(error.value)


def test_top_level_written_paths_match_declared_plan(tmp_path: Path) -> None:
    """The declared dry-run plan stays in sync with what generation actually writes."""
    from erenshor.application.wiki_lua.generation import planned_top_level_module_paths

    result = _run_generation(tmp_path)

    data_dir = tmp_path / "Erenshor" / "Data"
    written_top_level = [path for path in result.written_paths if path.parent == data_dir]
    assert written_top_level == planned_top_level_module_paths(tmp_path)


def test_generation_removes_stale_data_modules(tmp_path: Path) -> None:
    """Files left by a previous generation that are no longer produced are removed."""
    data_dir = tmp_path / "Erenshor" / "Data"
    stale_shard = data_dir / "Items" / "001.lua"
    stale_module = data_dir / "Obsolete.lua"
    stale_legacy_module = data_dir / "AbilityLinks.lua"
    stale_shard.parent.mkdir(parents=True)
    stale_shard.write_text("return {}\n", encoding="utf-8")
    stale_module.write_text("return {}\n", encoding="utf-8")
    stale_legacy_module.write_text("return {}\n", encoding="utf-8")

    result = _run_generation(tmp_path)

    assert not stale_shard.exists()
    assert not stale_module.exists()
    assert not stale_legacy_module.exists()
    assert (data_dir / "Items.lua") in result.written_paths
    assert (data_dir / "Items.lua").exists()


def test_orchestration_passes_reviewed_lifecycle_and_build_to_versioned_item_records(tmp_path: Path) -> None:
    from erenshor.application.wiki_lua.items_v2 import item_bucket

    key = "item:sword_of_flames"
    disposition = ItemDisposition(key, "removed", reason="Removed content")
    notice = LifecyclePage(
        title="Sword of Flames",
        stable_key=key,
        state="removed",
        thing="item",
        update="The Update",
        date=None,
        patch_notes_url=None,
        source="Reviewed item lifecycle",
    )
    _run_generation(
        tmp_path,
        provenance_repo=FakeItemProvenanceRepository([key], dispositions=[disposition]),
        lifecycle=ContentLifecycle({notice.title: notice}, {}, {}),
    )
    record = (tmp_path / "Erenshor" / "Data" / "ItemsV2" / f"{item_bucket(key)}.lua").read_text(encoding="utf-8")
    assert '["gameBuildId"] = "24405256"' in record
    assert '["publishedAt"] = "2026-07-27T12:34:56+00:00"' in record
    assert '["disposition"] = "removed"' in record
    assert '["update"] = "The Update"' in record


def test_generation_retains_historical_only_canonical_dispositions(tmp_path: Path) -> None:
    from erenshor.application.wiki_lua.items_v2 import item_bucket

    visible_key = "item:sword_of_flames"
    historical_key = "item:historical-only"
    result = _run_generation(
        tmp_path,
        provenance_repo=FakeItemProvenanceRepository(
            [visible_key],
            dispositions=[
                ItemDisposition(visible_key, "current"),
                ItemDisposition(historical_key, "removed", former_pages=("Historical Item",)),
            ],
        ),
    )
    data_dir = tmp_path / "Erenshor" / "Data"
    historical_path = data_dir / "ItemProvenanceV1" / f"{item_bucket(historical_key)}.lua"
    assert historical_path in result.written_paths
    assert historical_key in historical_path.read_text(encoding="utf-8")
    assert historical_key in (data_dir / "ItemsV2.lua").read_text(encoding="utf-8")
    assert all(historical_key not in path.read_text(encoding="utf-8") for path in (data_dir / "ItemsV2").glob("*.lua"))


def test_orchestration_writes_reviewed_nonitem_lifecycle_supplement(tmp_path: Path) -> None:
    page = LifecyclePage(
        title="Former Skill",
        stable_key="skill:former",
        state="removed",
        thing="skill",
        update="The Update",
        date=None,
        patch_notes_url=None,
        source="Reviewed shipped skill lifecycle",
    )
    _run_generation(tmp_path, lifecycle=ContentLifecycle({page.title: page}, {}, {}))

    content = (tmp_path / "Erenshor" / "Data" / "EntityLifecycle.lua").read_text(encoding="utf-8")
    assert '["skill:former"] = {' in content
    assert '["state"] = "removed"' in content
    assert '["update"] = "The Update"' in content
    assert "item:sword_of_flames" not in content


def test_generation_emits_every_stance_relation_and_current_removed_mana_notices(tmp_path: Path) -> None:
    lifecycle = load_content_lifecycle(Path(__file__).resolve().parents[4] / "content-lifecycle.json")
    stances = [
        make_stance(
            stable_key=f"stance:fixture:{index}", display_name=f"Fixture {index}", wiki_page_name=f"Fixture {index}"
        )
        for index in range(7)
    ]
    _run_generation(tmp_path, lifecycle=lifecycle, stance_repo=FakeStanceRepository(stances))

    data_dir = tmp_path / "Erenshor" / "Data"
    relations = (data_dir / "StanceRelations.lua").read_text(encoding="utf-8")
    assert relations.count('["activatedBy"] = {') == len(stances)
    for stance in stances:
        assert f'["{stance.stable_key}"] = {{' in relations
    notices = (data_dir / "EntityLifecycle.lua").read_text(encoding="utf-8")
    for title in ("Mana Burst", "Mana Call"):
        page = lifecycle.pages[title]
        assert page.state == "removed"
        assert f'["{page.stable_key}"] = {{' in notices


def test_entity_lifecycle_supplement_uses_the_normal_generation_size_limit(tmp_path: Path) -> None:
    page = LifecyclePage(
        title="Former Skill",
        stable_key="skill:former",
        state="removed",
        thing="skill",
        update="Reviewed lifecycle " * 2000,
        date=None,
        patch_notes_url=None,
        source="Reviewed skill lifecycle",
    )
    lifecycle = ContentLifecycle({page.title: page}, {}, {})
    reference_root = tmp_path / "reference"
    result = _run_generation(reference_root, lifecycle=lifecycle)
    supplement = reference_root / "Erenshor" / "Data" / "EntityLifecycle.lua"
    limit = supplement.stat().st_size - 1
    assert all(path.stat().st_size <= limit for path in result.written_paths if path != supplement)

    with pytest.raises(ValueError, match="Module:Erenshor/Data/EntityLifecycle"):
        _run_generation(tmp_path / "rejected", lifecycle=lifecycle, max_page_bytes=limit)
    assert not (tmp_path / "rejected").exists()


def test_character_seam_preserves_exact_copy_facts_and_canonical_item_lifecycle() -> None:
    representative = make_character(stable_key="character:representative", has_stats=0, class_resource_name="NativeNPC")
    copy = representative.model_copy(update={"stable_key": "character:copy"})
    hidden_item = "item:hidden-loot"
    item_disposition = ItemDisposition(hidden_item, "removed", former_pages=("Hidden Loot",))
    drop = ItemAcquisition(
        "drop:copy:slot:2",
        hidden_item,
        "character_drop",
        copy.stable_key,
        source_copy_stable_key=copy.stable_key,
        probability_kind="exact",
        probability_min=12.5,
        probability_max=12.5,
        quantity_min=2,
        quantity_max=2,
        quantity_kind="exact",
    )
    provenance = FakeItemProvenanceRepository(
        [hidden_item],
        acquisitions=[
            drop,
            ItemAcquisition("vendor:copy", hidden_item, "vendor", copy.stable_key),
            ItemAcquisition("dialog:copy", hidden_item, "dialog_reward", copy.stable_key),
            ItemAcquisition("global:copy", hidden_item, "special_world_drop", None),
            ItemAcquisition(
                "drop:unrelated",
                hidden_item,
                "character_drop",
                "character:unrelated",
                source_copy_stable_key="character:unrelated",
            ),
        ],
        dispositions=[item_disposition],
    )
    characters = FakeCharacterRepository(
        [representative],
        members={representative.stable_key: [representative, copy]},
        catalog={
            hidden_item: {"name": "Hidden Loot", "page": None},
            "faction:the_followers_of_evil": {"name": "The Followers of Evil", "page": "The Followers of Evil"},
        },
    )
    notice = LifecyclePage(
        title="A Grizzly Bear",
        stable_key=copy.stable_key,
        state="unused",
        thing="character",
        update=None,
        date=None,
        patch_notes_url=None,
        source="Reviewed character lifecycle",
        chat=True,
    )

    records = build_character_generation_records(
        character_repo=characters,
        provenance_repo=provenance,
        treasure_repo=FakeTreasureRepository(),
        catalog=characters.get_character_data_catalog(),
        class_labels={"NativeNPC": {"name": "Native NPC"}},
        constants=characters.get_character_data_spawn_constants(),
        mitigations={},
        build={"gameBuildId": "test-build", "publishedAt": "test-publication"},
        lifecycle=ContentLifecycle({notice.title: notice}, {}, {}),
        summoned_by_character={copy.stable_key: [{"key": "spell:pet", "name": "Pet Spell"}]},
        common_world_characters=frozenset({copy.stable_key}),
    )

    record = records[representative.stable_key]
    assert record["memberKeys"] == [copy.stable_key, representative.stable_key]
    assert len(record["loot"]) == 1
    assert record["loot"][0]["actionable"] is False
    assert record["loot"][0]["acquisition_key"] == drop.acquisition_key
    assert record["loot"][0]["source_copy_stable_key"] == copy.stable_key
    assert record["loot"][0]["item"]["disposition"] == fact_to_dict(item_disposition)
    assert "page" not in record["loot"][0]["item"]
    assert record["commonWorldDrops"] is True
    assert record["isSummon"] is True
    assert record["summonedBy"] == [{"key": "spell:pet", "name": "Pet Spell", "memberKey": copy.stable_key}]
    assert record["lifecycle"] == {"state": "unused", "thing": "character", "chat": True}
    assert all(
        variant["class"] == {"name": "Native NPC", "resourceName": "NativeNPC"} for variant in record["variants"]
    )


def test_full_generation_uses_resource_class_labels_and_exact_character_drops(tmp_path: Path) -> None:
    character = make_character(has_stats=0, class_resource_name="PlayableResource")
    npc_copy = character.model_copy(update={"stable_key": "character:npc-copy", "class_resource_name": "DefaultNPC"})
    item_key = make_item().stable_key
    drop = ItemAcquisition(
        "drop:character:2",
        item_key,
        "character_drop",
        character.stable_key,
        source_copy_stable_key=character.stable_key,
        quantity_min=1,
        quantity_max=1,
        quantity_kind="exact",
    )
    characters = FakeCharacterRepository(
        [character],
        members={character.stable_key: [character, npc_copy]},
        classes=[
            {
                "resource_name": "PlayableResource",
                "class_name": "Windblade",
                "display_name": "Native Name",
                "mitigation_bonus": 1,
            },
            {
                "resource_name": "DefaultNPC",
                "class_name": "Default",
                "display_name": "Native NPC",
                "mitigation_bonus": 1,
            },
        ],
    )
    result = _run_generation(
        tmp_path,
        character_repo=characters,
        provenance_repo=FakeItemProvenanceRepository([item_key], acquisitions=[drop]),
    )
    data_dir = tmp_path / "Erenshor" / "Data"
    index = data_dir / "Characters.lua"
    assert index in result.written_paths
    assert character.stable_key in index.read_text(encoding="utf-8")
    [shard] = list((data_dir / "Characters").glob("*.lua"))
    content = shard.read_text(encoding="utf-8")
    assert '["name"] = "Windblade"' in content
    assert '["page"] = "Windblade"' in content
    assert '["name"] = "Native NPC"' in content
    assert '["resourceName"] = "PlayableResource"' in content
    assert '["resourceName"] = "DefaultNPC"' in content
    assert '["page"] = "Default"' not in content
    assert '["actionable"] = true' in content
    assert drop.acquisition_key in content
    assert '["source_copy_stable_key"] = "character:a_grizzly_bear"' in content


def test_full_generation_replays_native_startup_profiles_and_initialized_rewards(tmp_path: Path) -> None:
    character = make_character(
        has_stats=1,
        is_npc=1,
        class_resource_name="DefaultNPC",
        start_components_listed="Character,Stats,NPC",
        is_active_at_load=0,
        base_hp=100,
        effective_hp=228,
        hard_set_ac=0,
        initialized_xp=72,
        xp_per_player_level=None,
        effective_xp_multiplier=1,
    )
    characters = FakeCharacterRepository(
        [character],
        classes=[
            {
                "resource_name": "DefaultNPC",
                "class_name": "Default",
                "display_name": "Native NPC",
                "mitigation_bonus": 1,
            },
        ],
    )
    _run_generation(tmp_path, character_repo=characters)

    [shard] = list((tmp_path / "Erenshor" / "Data" / "Characters").glob("*.lua"))
    content = shard.read_text(encoding="utf-8")
    assert '["profiles"] = {' in content
    assert '["baseExperience"] = 72' in content
    assert '["experienceMin"] = 72' in content
    assert '["experienceMax"] = 72' in content
