from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def acceptance() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wiki_dev_acceptance", Path("wiki-dev/acceptance.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Client:
    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _browser(module: ModuleType) -> dict[str, int]:
    return {key: index for index, key in enumerate(module.BROWSER_COUNTER_KEYS)}


def test_capture_acceptance_captures_sorted_content_cargo_and_smoke(
    acceptance: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path
    fixture_dir = root / "wiki-dev" / "fixtures"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "smoke.tsv").write_text("Smoke\tneedle\n", encoding="utf-8")
    (fixture_dir / "cargo_items.tsv").write_text("declared\n", encoding="utf-8")

    pages = [
        SimpleNamespace(title="MediaWiki:Common.js", content_model="javascript"),
        SimpleNamespace(title="Module:Z", content_model="Scribunto"),
        SimpleNamespace(title="Module:A", content_model="Scribunto"),
    ]
    monkeypatch.setattr(acceptance, "discover_pages", lambda root: pages)
    monkeypatch.setattr(
        acceptance,
        "query_remote_pages",
        lambda client, endpoint, titles: {
            "MediaWiki:Common.js": SimpleNamespace(content="js", content_model="javascript"),
            "Module:Z": SimpleNamespace(content="z", content_model="Scribunto"),
            "Module:A": SimpleNamespace(content="a", content_model="Scribunto"),
        },
    )
    monkeypatch.setattr(acceptance, "parse_page", lambda client, endpoint, title: f"needle parsed:{title}")
    monkeypatch.setattr(acceptance.httpx, "Client", _Client)
    monkeypatch.setattr(acceptance, "_CARGO_SPECS", (("Items", "FAKE_FIELDS", "fake_loader", "cargo_items.tsv"),))
    monkeypatch.setattr(acceptance._cargo_check, "FAKE_FIELDS", ("Page", "StableKey"), raising=False)
    monkeypatch.setattr(
        acceptance._cargo_check,
        "fake_loader",
        lambda path: [SimpleNamespace(page="declared")],
        raising=False,
    )
    monkeypatch.setattr(
        acceptance,
        "query_cargo_table",
        lambda client, endpoint, table, fields: [
            {"Page": "other", "StableKey": "x"},
            {"StableKey": "b", "Page": "declared"},
            {"Page": "declared", "StableKey": "a"},
        ],
    )

    snapshot = acceptance.capture_acceptance(root, "http://local", _browser(acceptance))

    assert snapshot.lua_modules == ("Module:A", "Module:Z")
    assert snapshot.interface_gadgets == ("MediaWiki:Common.js",)
    assert list(snapshot.cargo_rows["Items"]) == [
        {"Page": "declared", "StableKey": "a"},
        {"Page": "declared", "StableKey": "b"},
    ]
    assert set(snapshot.smoke_results) == {"Smoke"}
    assert snapshot.to_payload()["schema_version"] == acceptance.SCHEMA_VERSION


def test_capture_acceptance_propagates_missing_and_model_mismatch(
    acceptance: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = SimpleNamespace(title="Module:One", content_model="Scribunto")
    monkeypatch.setattr(acceptance, "discover_pages", lambda root: [page])
    monkeypatch.setattr(acceptance.httpx, "Client", _Client)
    monkeypatch.setattr(acceptance, "_CARGO_SPECS", ())
    monkeypatch.setattr(acceptance, "load_expectations", lambda path: {})

    monkeypatch.setattr(acceptance, "query_remote_pages", lambda *args: {"Module:One": None})
    with pytest.raises(RuntimeError, match="missing"):
        acceptance.capture_acceptance(tmp_path, "http://local", _browser(acceptance))

    monkeypatch.setattr(
        acceptance,
        "query_remote_pages",
        lambda *args: {"Module:One": SimpleNamespace(content="x", content_model="wikitext")},
    )
    with pytest.raises(RuntimeError, match="content model mismatch"):
        acceptance.capture_acceptance(tmp_path, "http://local", _browser(acceptance))


def test_capture_acceptance_rejects_failed_smoke(
    acceptance: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_dir = tmp_path / "wiki-dev" / "fixtures"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "smoke.tsv").write_text("Smoke\trequired\n", encoding="utf-8")
    monkeypatch.setattr(acceptance, "discover_pages", lambda root: [])
    monkeypatch.setattr(acceptance, "query_remote_pages", lambda *args: {})
    monkeypatch.setattr(acceptance, "parse_page", lambda *args: "wrong")
    monkeypatch.setattr(acceptance.httpx, "Client", _Client)
    monkeypatch.setattr(acceptance, "_CARGO_SPECS", ())

    with pytest.raises(RuntimeError, match="Smoke check failed for Smoke"):
        acceptance.capture_acceptance(tmp_path, "http://local", _browser(acceptance))


def test_compare_acceptance_reports_precise_deterministic_paths(acceptance: ModuleType) -> None:
    common = {
        "managed_pages": {"Page": {"content_model": "wikitext", "sha256": "a"}},
        "lua_modules": ("Module:A",),
        "interface_gadgets": ("MediaWiki:A",),
        "cargo_rows": {"Items": ({"Page": "Item", "Name": "old"},)},
        "smoke_results": {"Page": "old"},
        "browser_counters": dict.fromkeys(acceptance.BROWSER_COUNTER_KEYS, 0),
    }
    warm = acceptance.WikiAcceptanceSnapshot(**common)
    changed = dict(common)
    changed["managed_pages"] = {"Page": {"content_model": "wikitext", "sha256": "b"}}
    changed["cargo_rows"] = {"Items": ({"Page": "Item", "Name": "new"},)}
    changed["smoke_results"] = {"Page": "new"}
    changed["browser_counters"] = {**common["browser_counters"], "failed": 1}

    paths = acceptance.compare_acceptance(warm, acceptance.WikiAcceptanceSnapshot(**changed))

    assert paths == [
        "browser_counters.failed",
        "cargo_rows.Items[0].Name",
        "managed_pages.Page.sha256",
        "smoke_results.Page",
    ]
    assert paths == acceptance.compare_acceptance(warm, acceptance.WikiAcceptanceSnapshot(**changed))
