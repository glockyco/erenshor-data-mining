"""Hermetic tests for the CodeFacts analyzer against a fixture-built DLL."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed"),
]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "src" / "tools" / "CodeFacts"
FIXTURE_PROJ = TOOL / "tests" / "FixtureLib"
SPECS = REPO_ROOT / "tests" / "fixtures" / "code_facts" / "fixture-specs.json"


@pytest.fixture(scope="module")
def fixture_dll(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("fixture") / "Managed"  # satisfies the /Managed/ path gate
    subprocess.run(
        ["dotnet", "build", str(FIXTURE_PROJ), "-c", "Release", "-o", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    # Pre-build the analyzer so `dotnet run --no-build` emits only the tool's
    # JSON on stdout (a lazy build would interleave MSBuild output there).
    subprocess.run(
        ["dotnet", "build", str(TOOL), "-c", "Release"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out / "FixtureLib.dll"


def run_tool(dll: Path, specs: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        ["dotnet", "run", "-c", "Release", "--no-build", "--project", str(TOOL), "--", str(dll), str(specs)],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def test_extracts_guarded_rolls_and_strings(fixture_dll: Path) -> None:
    rc, out = run_tool(fixture_dll, SPECS)
    assert rc == 0, out
    facts = {f["id"]: f for f in out["facts"]}
    assert facts["fixture.pool_a"]["values"] == {"rate": "0.005", "min_level": "0"}
    assert facts["fixture.singleton_b"]["values"] == {"rate": "0.0125", "min_level": "20"}
    assert facts["fixture.combine_ids"]["values"] == {"strings": "31377423,46289586"}
    assert facts["fixture.auction_envelope"]["values"] == {"level": "> 0,< 40", "value": "> 0"}


def test_unmatched_spec_fails_loud(fixture_dll: Path, tmp_path: Path) -> None:
    specs = json.loads(SPECS.read_text())
    specs["facts"][0]["args"]["member"] = "NoSuchPool"
    bad = tmp_path / "bad-specs.json"
    bad.write_text(json.dumps(specs))
    rc, out = run_tool(fixture_dll, bad)
    assert rc == 1
    assert any("fixture.pool_a" in e for e in out["errors"])
