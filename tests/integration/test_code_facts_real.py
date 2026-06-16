"""Shape assertions against the real main-variant binary (no exact values)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DLL = REPO_ROOT / "variants" / "main" / "game" / "Erenshor_Data" / "Managed" / "Assembly-CSharp.dll"
TOOL = REPO_ROOT / "src" / "tools" / "CodeFacts"
SPECS = TOOL / "specs" / "erenshor-facts.json"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed"),
    pytest.mark.skipif(not DLL.exists(), reason="main variant game files not present"),
]


def test_all_facts_extract_with_sane_shapes(code_facts_tool: Path) -> None:
    proc = subprocess.run(
        ["dotnet", "run", "-c", "Release", "--no-build", "--project", str(code_facts_tool), "--", str(DLL), str(SPECS)],
        capture_output=True,
        text=True,
        check=False,
    )
    out = json.loads(proc.stdout)
    assert proc.returncode == 0, out.get("errors")

    spec_ids = {f["id"] for f in json.loads(SPECS.read_text())["facts"]}
    got = {f["id"]: f for f in out["facts"]}
    assert set(got) == spec_ids

    for fact in got.values():
        if fact["mode"] != "extract":
            continue
        values = fact["values"]
        if "rate" in values:
            assert 0.0 < float(values["rate"]) <= 1.0, fact["id"]
            assert int(values["min_level"]) >= 0, fact["id"]
        if "strings" in values:
            assert all(s.isdigit() for s in values["strings"].split(",")), fact["id"]
