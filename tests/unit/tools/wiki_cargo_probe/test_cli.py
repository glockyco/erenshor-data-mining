from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from erenshor.tools.wiki_cargo_probe import cli

if TYPE_CHECKING:
    import pytest


def test_lifecycle_dry_run_main_reports_pages_tables_and_manual_cleanup_urls(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_live_config_is_loaded() -> None:
        raise AssertionError("dry-run main must not load live wiki configuration")

    monkeypatch.setattr(cli, "load_config", fail_if_live_config_is_loaded)

    exit_code = cli.main(["--candidate", "lifecycle", "--prefix", "UnitProbe"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    dry_run = payload["dry_run"]
    assert dry_run["live"] is False
    assert dry_run["candidate"] == "lifecycle"
    assert dry_run["prefix"] == "UnitProbe"
    assert dry_run["batch_pages"] == 25
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


def test_multi_entity_dry_run_main_reports_pages_tables_and_manual_cleanup_urls(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_live_config_is_loaded() -> None:
        raise AssertionError("dry-run main must not load live wiki configuration")

    monkeypatch.setattr(cli, "load_config", fail_if_live_config_is_loaded)

    exit_code = cli.main(["--candidate", "multi-entity", "--prefix", "UnitProbe"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    dry_run = payload["dry_run"]
    assert dry_run["live"] is False
    assert dry_run["candidate"] == "multi-entity"
    assert dry_run["prefix"] == "UnitProbe"
    assert dry_run["pages"] == [
        "User:WoWMuch/CargoStorageProbe/UnitProbe/MultiEntity",
        "Module:CargoStorageProbe/UnitProbeMultiEntity/Lifecycle",
        "Template:CargoStorageProbe/UnitProbeMultiEntity/LifecycleMain",
        "Template:CargoStorageProbe/UnitProbeMultiEntity/LifecycleObtainedFromStore",
        "Template:CargoStorageProbe/UnitProbeMultiEntity/LifecycleUsedInStore",
    ]
    assert dry_run["tables"] == [
        "UnitProbeMultiEntityLifecycleItems",
        "UnitProbeMultiEntityLifecycleObtainedFrom",
        "UnitProbeMultiEntityLifecycleUsedIn",
    ]
    assert dry_run["manual_table_cleanup_urls"] == [
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeMultiEntityLifecycleItems",
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeMultiEntityLifecycleObtainedFrom",
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeMultiEntityLifecycleUsedIn",
    ]


def test_recreate_batching_dry_run_main_reports_pages_tables_and_manual_cleanup_urls(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_live_config_is_loaded() -> None:
        raise AssertionError("dry-run main must not load live wiki configuration")

    monkeypatch.setattr(cli, "load_config", fail_if_live_config_is_loaded)

    exit_code = cli.main(["--candidate", "recreate-batching", "--prefix", "UnitProbe", "--batch-pages", "3"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    dry_run = payload["dry_run"]
    assert dry_run["live"] is False
    assert dry_run["candidate"] == "recreate-batching"
    assert dry_run["prefix"] == "UnitProbe"
    assert dry_run["batch_pages"] == 3
    assert dry_run["pages"] == [
        "User:WoWMuch/CargoStorageProbe/UnitProbe/RecreateBatching/Page0001",
        "User:WoWMuch/CargoStorageProbe/UnitProbe/RecreateBatching/Page0002",
        "User:WoWMuch/CargoStorageProbe/UnitProbe/RecreateBatching/Page0003",
        "Module:CargoStorageProbe/UnitProbeBatch/Lifecycle",
        "Template:CargoStorageProbe/UnitProbeBatch/LifecycleMain",
        "Template:CargoStorageProbe/UnitProbeBatch/LifecycleObtainedFromStore",
        "Template:CargoStorageProbe/UnitProbeBatch/LifecycleUsedInStore",
    ]
    assert dry_run["tables"] == [
        "UnitProbeBatchLifecycleItems",
        "UnitProbeBatchLifecycleObtainedFrom",
        "UnitProbeBatchLifecycleUsedIn",
    ]
    assert dry_run["manual_table_cleanup_urls"] == [
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeBatchLifecycleItems",
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeBatchLifecycleObtainedFrom",
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeBatchLifecycleUsedIn",
    ]


def test_replacement_table_dry_run_reports_original_and_next_cleanup_urls(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_live_config_is_loaded() -> None:
        raise AssertionError("dry-run main must not load live wiki configuration")

    monkeypatch.setattr(cli, "load_config", fail_if_live_config_is_loaded)

    exit_code = cli.main(["--candidate", "replacement-table", "--prefix", "UnitProbe"])

    assert exit_code == 0
    dry_run = json.loads(capsys.readouterr().out)["dry_run"]
    assert dry_run["live"] is False
    assert dry_run["candidate"] == "replacement-table"
    assert dry_run["prefix"] == "UnitProbe"
    assert dry_run["pages"] == [
        "User:WoWMuch/CargoStorageProbe/UnitProbe/Replacement",
        "Template:CargoStorageProbe/UnitProbe/Replacement",
    ]
    assert dry_run["tables"] == ["UnitProbeReplacementItems", "UnitProbeReplacementItems__NEXT"]
    assert dry_run["manual_table_cleanup_urls"] == [
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeReplacementItems",
        "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/UnitProbeReplacementItems__NEXT",
    ]


def test_shim_import_exposes_main_and_keeps_dry_run_path(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_live_config_is_loaded() -> None:
        raise AssertionError("dry-run main must not load live wiki configuration")

    monkeypatch.setattr(cli, "load_config", fail_if_live_config_is_loaded)
    module_path = Path(__file__).parents[4] / "src" / "tools" / "wiki_cargo_storage_probe.py"
    spec = importlib.util.spec_from_file_location("wiki_cargo_storage_probe_shim_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert isinstance(module, ModuleType)
    assert module.main is cli.main
    assert module.main(["--candidate", "lifecycle", "--prefix", "UnitProbe"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"]["candidate"] == "lifecycle"
    assert payload["dry_run"]["pages"][0] == "User:WoWMuch/CargoStorageProbe/UnitProbe/Lifecycle"
