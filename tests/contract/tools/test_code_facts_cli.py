"""Hermetic tests for the CodeFacts analyzer against a fixture-built DLL."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")

REPO_ROOT = Path(__file__).resolve().parents[3]
SPECS = REPO_ROOT / "tests" / "fixtures" / "code_facts" / "fixture-specs.json"


def run_tool(tool: Path, dll: Path, specs: Path) -> tuple[int, dict]:
    command = [
        "dotnet",
        "run",
        "-c",
        "Release",
        "--no-build",
        "--project",
        str(tool),
        "--",
        str(dll),
        str(specs),
    ]
    proc = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def test_cli_serializes_successful_fixture_run(
    fixture_dll: Path,
    code_facts_tool: Path,
) -> None:
    rc, out = run_tool(code_facts_tool, fixture_dll, SPECS)
    assert rc == 0, out
    assert out["schema"] == 1
    assert out["assembly"] == str(fixture_dll)

    facts = {fact["id"]: fact for fact in out["facts"]}
    assert facts["fixture.pool_a"]["values"] == {"rate": "0.005", "min_level": "0"}
    assert facts["fixture.singleton_b"]["values"] == {"rate": "0.0125", "min_level": "20"}
    assert facts["fixture.combine_ids"]["values"] == {"strings": "31377423,46289586"}
    assert facts["fixture.auction_envelope"]["values"] == {"level": "> 0,< 40", "value": "> 0"}

    for fact_id in (
        "fixture.guarantee_shape",
        "fixture.guarantee_retry_loop",
        "fixture.trigger_strings",
    ):
        assert facts[fact_id]["ok"] is True
        assert facts[fact_id]["values"] is None
    assert out["errors"] == []
