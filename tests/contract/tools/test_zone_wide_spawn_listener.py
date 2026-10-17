"""Exercise candidate slots through the production zone-wide export listener."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")
_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "zone_wide_spawns"


def test_zone_wide_candidates_preserve_weight_without_placements(
    tmp_path: Path, dotnet_build: Callable[..., None]
) -> None:
    out = tmp_path / "build"
    dotnet_build(_PROJECT, "-o", str(out), f"-p:BaseIntermediateOutputPath={tmp_path / 'obj'}/")
    result = subprocess.run(
        ["dotnet", str(out / "ZoneWideSpawnsFixture.dll")], capture_output=True, text=True, check=True
    )
    payload = json.loads(result.stdout)
    assert [(row["Slot"], row["CharacterStableKey"]) for row in payload["rows"]] == [
        (0, "character:first"),
        (1, "character:second"),
        (2, "character:first"),
    ]
    assert [row["Key"] for row in payload["rows"]] == [f"sivakayan_spectres:{slot}" for slot in range(3)]
    assert all(row["RuleId"] == "sivakayan_spectres" for row in payload["rows"])
    assert len(payload["replacement"]) == 1
    assert payload["replacement"][0]["CharacterStableKey"] == "character:second"
    assert payload["failures"] == [
        "Expected one placed Misc, found 0",
        "Expected one placed Misc, found 2",
        "Misc.SivakayanSpectres has no candidates",
        "Misc.SivakayanSpectres[0] has no Character",
        "Misc.SivakayanSpectres[0] has no Character",
    ]
