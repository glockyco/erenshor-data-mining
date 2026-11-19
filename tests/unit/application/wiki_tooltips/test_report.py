import hashlib
from pathlib import Path

import pytest
from tests.unit.application.wiki_tooltips.test_capture import make_database, observations

from erenshor.application.wiki_tooltips.capture import reconcile
from erenshor.application.wiki_tooltips.report import ParityPaths, read_json, require_current, write_json


@pytest.fixture
def parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ParityPaths:
    paths = ParityPaths(tmp_path, tmp_path / "clean.sqlite", tmp_path / "variants/playtest/wiki")
    make_database(paths.database)
    entries = observations()
    exclusions = reconcile(paths.database, entries)
    write_json(
        paths.evidence,
        {"build": "100", "installed_build": "100", "failures": [], "entries": entries, "exclusions": exclusions},
    )
    inputs = (
        paths.root / "wiki/templates/SpellTooltip.wiki",
        paths.wiki / "lua/Erenshor/Data/Spells.lua",
        paths.evidence,
    )
    for path in inputs[:-1]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original")
    monkeypatch.setattr(
        ParityPaths,
        "inputs",
        lambda _: {str(path.relative_to(paths.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    )
    write_json(
        paths.report,
        {
            "build": "100",
            "schema": 1,
            "complete": True,
            "findings": [],
            "exclusions": exclusions,
            "coverage": {"spell": 1, "skill": 1, "stance": 1, "item_cards": 0},
            "inputs": paths.inputs(),
        },
    )
    return paths


def test_current_complete_report_passes(parity: ParityPaths) -> None:
    require_current(parity)


@pytest.mark.parametrize(
    "relative", ["wiki/templates/SpellTooltip.wiki", "variants/playtest/wiki/lua/Erenshor/Data/Spells.lua"]
)
def test_changed_renderer_input_is_reported(parity: ParityPaths, relative: str) -> None:
    (parity.root / relative).write_text("changed")
    with pytest.raises(ValueError, match="changed inputs"):
        require_current(parity)


@pytest.mark.parametrize(
    ("report_field", "value", "message"),
    [
        ("build", "200", "expected clean database build 100"),
        ("findings", [{"error": "missing resist row"}], "comparison did not finish"),
        ("coverage", {"item_cards": 0}, "expected complete coverage"),
    ],
)
def test_report_rejects_wrong_build_failure_and_incomplete_coverage(parity, report_field, value, message) -> None:
    report = read_json(parity.report)
    report[report_field] = value
    write_json(parity.report, report)
    with pytest.raises(ValueError, match=message):
        require_current(parity)


def test_report_rejects_incomplete_collection(parity: ParityPaths) -> None:
    evidence = read_json(parity.evidence)
    evidence["entries"].pop()
    write_json(parity.evidence, evidence)
    with pytest.raises(ValueError, match="Incomplete skill:guard"):
        require_current(parity)
