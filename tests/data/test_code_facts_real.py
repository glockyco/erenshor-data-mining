"""Shape assertions against the real main-variant binary (no exact values)."""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "src" / "tools" / "CodeFacts"
SPECS = TOOL / "specs" / "erenshor-facts.json"


def test_all_facts_extract_with_sane_shapes(code_facts_tool: Path, shipped_main_dll: Path) -> None:
    proc = subprocess.run(
        [
            "dotnet",
            "run",
            "-c",
            "Release",
            "--no-build",
            "--project",
            str(code_facts_tool),
            "--",
            str(shipped_main_dll),
            str(SPECS),
            "--variant",
            "main",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    out = json.loads(proc.stdout)
    assert proc.returncode == 0, out.get("errors")

    specs = json.loads(SPECS.read_text())["facts"]
    spec_ids = {f["id"] for f in specs if "main" in f.get("variants", ["main"])}
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
