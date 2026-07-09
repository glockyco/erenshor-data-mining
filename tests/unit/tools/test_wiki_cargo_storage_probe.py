from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def probe_module() -> ModuleType:
    module_path = Path(__file__).parents[3] / "src" / "tools" / "wiki_cargo_storage_probe.py"
    spec = importlib.util.spec_from_file_location("wiki_cargo_storage_probe_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lifecycle_candidate_builds_isolated_pages_tables_and_state_transitions(probe_module: ModuleType) -> None:
    candidate = probe_module.build_lifecycle_candidate("UnitProbe")

    assert candidate.kind == "lifecycle"
    assert candidate.page_title == "User:WoWMuch/CargoStorageProbe/UnitProbe/Lifecycle"
    assert candidate.template_base == "CargoStorageProbe/UnitProbe/Lifecycle"
    assert candidate.item_key == "UnitProbeLifecycleItemA"
    assert candidate.removed_key == "UnitProbeLifecycleItemB"
    assert candidate.tables == {
        "Items": "UnitProbeLifecycleItems",
        "ObtainedFrom": "UnitProbeLifecycleObtainedFrom",
        "UsedIn": "UnitProbeLifecycleUsedIn",
    }

    templates_by_title = {template.title: template.content for template in candidate.templates}
    assert set(templates_by_title) == {
        "Module:CargoStorageProbe/UnitProbe/Lifecycle",
        "Template:CargoStorageProbe/UnitProbe/LifecycleMain",
        "Template:CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore",
        "Template:CargoStorageProbe/UnitProbe/LifecycleUsedInStore",
    }

    module_content = templates_by_title["Module:CargoStorageProbe/UnitProbe/Lifecycle"]
    assert "local tables = { Items = 'UnitProbeLifecycleItems'" in module_content
    assert "ObtainedFrom = 'UnitProbeLifecycleObtainedFrom'" in module_content
    assert "UsedIn = 'UnitProbeLifecycleUsedIn'" in module_content
    assert "function p.storeObtainedFrom(frame)" in module_content
    assert "function p.storeUsedIn(frame)" in module_content
    assert "__ITEMS__" not in module_content
    assert "__OBTAINED_FROM__" not in module_content
    assert "__USED_IN__" not in module_content

    main_template = templates_by_title["Template:CargoStorageProbe/UnitProbe/LifecycleMain"]
    assert "#cargo_declare:_table=UnitProbeLifecycleItems" in main_template
    assert "StableKey=String" in main_template
    assert "DisplayName=String" in main_template
    assert "#invoke:CargoStorageProbe/UnitProbe/Lifecycle|storeItem" in main_template
    assert "CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore" in main_template
    assert "CargoStorageProbe/UnitProbe/LifecycleUsedInStore" in main_template

    obtained_template = templates_by_title["Template:CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore"]
    assert "#cargo_declare:_table=UnitProbeLifecycleObtainedFrom" in obtained_template
    assert "ItemKey=String" in obtained_template
    assert "SourceKey=String" in obtained_template
    assert "SourceIndex=Integer" in obtained_template

    used_template = templates_by_title["Template:CargoStorageProbe/UnitProbe/LifecycleUsedInStore"]
    assert "#cargo_declare:_table=UnitProbeLifecycleUsedIn" in used_template
    assert "ItemKey=String" in used_template
    assert "UseKey=String" in used_template
    assert "UseIndex=Integer" in used_template

    assert candidate.recreate_templates == (
        "CargoStorageProbe/UnitProbe/LifecycleMain",
        "CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore",
        "CargoStorageProbe/UnitProbe/LifecycleUsedInStore",
    )
    assert candidate.recreatedata_pairs == (
        ("CargoStorageProbe/UnitProbe/LifecycleMain", "UnitProbeLifecycleItems"),
        ("CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore", "UnitProbeLifecycleObtainedFrom"),
        ("CargoStorageProbe/UnitProbe/LifecycleUsedInStore", "UnitProbeLifecycleUsedIn"),
    )

    assert "|stablekey=UnitProbeLifecycleItemA" in candidate.initial_content
    assert "|stablekey=UnitProbeLifecycleItemB" in candidate.initial_content
    assert "|source1=SourceA1" in candidate.initial_content
    assert "|source2=SourceA2" in candidate.initial_content
    assert "|source3=SourceA3" in candidate.initial_content
    assert "|use1=UseA1" in candidate.initial_content
    assert "|source1=SourceB1" in candidate.initial_content
    assert "|use1=UseB1" in candidate.initial_content

    assert "|stablekey=UnitProbeLifecycleItemA" in candidate.reduced_content
    assert "|stablekey=UnitProbeLifecycleItemB" in candidate.reduced_content
    assert "|source1=SourceA1" in candidate.reduced_content
    assert "|source2=SourceA2" not in candidate.reduced_content
    assert "|source3=SourceA3" not in candidate.reduced_content
    assert "|use1=UseA1" not in candidate.reduced_content
    assert "|use1=UseB1" in candidate.reduced_content

    assert "|stablekey=UnitProbeLifecycleItemA" in candidate.removed_content
    assert "|source1=SourceA1" in candidate.removed_content
    assert "UnitProbeLifecycleItemB" not in candidate.removed_content
    assert "UseB1" not in candidate.removed_content


def test_lifecycle_dry_run_main_reports_pages_tables_and_manual_cleanup_urls(
    probe_module: ModuleType, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_live_config_is_loaded() -> None:
        raise AssertionError("dry-run main must not load live wiki configuration")

    monkeypatch.setattr(probe_module, "load_config", fail_if_live_config_is_loaded)

    exit_code = probe_module.main(["--candidate", "lifecycle", "--prefix", "UnitProbe"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    dry_run = payload["dry_run"]
    assert dry_run["live"] is False
    assert dry_run["candidate"] == "lifecycle"
    assert dry_run["prefix"] == "UnitProbe"
    assert dry_run["pages"] == [
        "User:WoWMuch/CargoStorageProbe/UnitProbe/Lifecycle",
        "Module:CargoStorageProbe/UnitProbe/Lifecycle",
        "Template:CargoStorageProbe/UnitProbe/LifecycleMain",
        "Template:CargoStorageProbe/UnitProbe/LifecycleObtainedFromStore",
        "Template:CargoStorageProbe/UnitProbe/LifecycleUsedInStore",
    ]
    assert dry_run["tables"] == [
        "UnitProbeLifecycleItems",
        "UnitProbeLifecycleObtainedFrom",
        "UnitProbeLifecycleUsedIn",
    ]
    assert dry_run["manual_table_cleanup_urls"] == [
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeLifecycleItems",
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeLifecycleObtainedFrom",
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeLifecycleUsedIn",
    ]
