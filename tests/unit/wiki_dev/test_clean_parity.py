from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_clean_parity() -> ModuleType:
    script = Path("wiki-dev/clean_parity.py")
    spec = importlib.util.spec_from_file_location("wiki_dev_clean_parity", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Snapshot:
    def __init__(self, marker: str = "same") -> None:
        self.marker = marker

    def to_payload(self) -> dict[str, object]:
        return {"marker": self.marker}


def make_harness(module: ModuleType, tmp_path: Path):
    root = tmp_path / "repo"
    manifest = root / "wiki-dev" / "runtime" / "import_pages.manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"warm manifest\n")
    work = tmp_path / "work"
    work.mkdir()
    return module.CleanParityHarness(
        root=root,
        warm_base_url="http://localhost:8088",
        warm_project="wiki-dev",
        clean_base_url="http://127.0.0.1:18088",
        clean_project="wiki-clean-test",
        clean_port=18088,
        work_directory=work,
    )


def test_bootstrap_failure_still_tears_down_and_rechecks_warm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_clean_parity()
    harness = make_harness(module, tmp_path)
    events: list[str] = []
    snapshot = _Snapshot()
    monkeypatch.setattr(harness, "_validate_stack", lambda **_kwargs: dict.fromkeys(module.BROWSER_COUNTER_KEYS, 0))
    monkeypatch.setattr(module, "capture_acceptance", lambda *_args: snapshot)
    monkeypatch.setattr(module, "compare_acceptance", lambda _left, _right: [])

    def fail_bootstrap() -> None:
        events.append("bootstrap")
        raise module.CommandFailureError("bootstrap failed")

    monkeypatch.setattr(harness, "_bootstrap_clean_stack", fail_bootstrap)
    monkeypatch.setattr(harness, "_teardown_clean_stack", lambda: events.append("teardown"))

    with pytest.raises(module.CommandFailureError, match="bootstrap failed"):
        harness.run()

    assert events == ["bootstrap", "teardown"]


def test_clean_difference_tears_down_and_reports_precise_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_clean_parity()
    harness = make_harness(module, tmp_path)
    captures = iter((_Snapshot("warm"), _Snapshot("clean"), _Snapshot("warm")))
    events: list[str] = []
    monkeypatch.setattr(harness, "_validate_stack", lambda **_kwargs: dict.fromkeys(module.BROWSER_COUNTER_KEYS, 0))
    monkeypatch.setattr(module, "capture_acceptance", lambda *_args: next(captures))
    monkeypatch.setattr(
        module,
        "compare_acceptance",
        lambda left, right: [] if left.marker == right.marker else ["managed_pages.Page.sha256"],
    )
    monkeypatch.setattr(harness, "_bootstrap_clean_stack", lambda: events.append("bootstrap"))
    monkeypatch.setattr(harness, "_teardown_clean_stack", lambda: events.append("teardown"))

    with pytest.raises(RuntimeError, match=r"managed_pages\.Page\.sha256"):
        harness.run()

    assert events == ["bootstrap", "teardown"]


def test_warm_manifest_mutation_takes_precedence_over_clean_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_clean_parity()
    harness = make_harness(module, tmp_path)
    snapshot = _Snapshot()
    monkeypatch.setattr(harness, "_validate_stack", lambda **_kwargs: dict.fromkeys(module.BROWSER_COUNTER_KEYS, 0))
    monkeypatch.setattr(module, "capture_acceptance", lambda *_args: snapshot)
    monkeypatch.setattr(module, "compare_acceptance", lambda _left, _right: [])

    def mutate_then_fail() -> None:
        manifest = harness.root / "wiki-dev" / "runtime" / "import_pages.manifest.json"
        manifest.write_bytes(b"mutated\n")
        raise RuntimeError("clean failed")

    monkeypatch.setattr(harness, "_bootstrap_clean_stack", mutate_then_fail)
    monkeypatch.setattr(harness, "_teardown_clean_stack", lambda: None)

    with pytest.raises(RuntimeError, match="managed import manifest bytes changed") as error:
        harness.run()

    assert isinstance(error.value.__cause__, RuntimeError)
    assert str(error.value.__cause__) == "clean failed"


def test_project_validation_rejects_warm_and_invalid_names() -> None:
    module = load_clean_parity()

    assert module._validate_project("wiki-clean-123", warm_project="wiki-dev") == "wiki-clean-123"
    with pytest.raises(ValueError, match="must differ"):
        module._validate_project("wiki-dev", warm_project="wiki-dev")
    with pytest.raises(ValueError, match="Invalid"):
        module._validate_project("Wiki Clean", warm_project="wiki-dev")
