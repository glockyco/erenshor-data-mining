"""Execute the authored-sim listener without Unity or a live game."""

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
_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "authored_sims"


def test_authored_sim_listener_uses_only_explicit_references(tmp_path: Path, dotnet_build: Callable[..., None]) -> None:
    out = tmp_path / "build"
    dotnet_build(_PROJECT, "-o", str(out), f"-p:BaseIntermediateOutputPath={tmp_path / 'obj'}/")
    result = subprocess.run(
        ["dotnet", str(out / "AuthoredSimsFixture.dll")], capture_output=True, text=True, check=True
    )
    payload = json.loads(result.stdout)
    sims = {row["StableKey"]: row for row in payload["sims"]}
    assert set(sims) == {"authored_sim:guid-a:100", "authored_sim:guid-b:100"}
    assert {row["StableKey"] for row in payload["reordered"]} == set(sims)
    assert [row["AuthoredSimStableKey"] for row in payload["references"]] == [
        "authored_sim:guid-a:100",
        "authored_sim:guid-b:100",
        "authored_sim:guid-a:100",
    ]
    assert [row["ReferenceIndex"] for row in payload["references"]] == [0, 1, 2]
    assert {row["SourceComponentKey"] for row in payload["references"]} == {"manager:1"}
    for key, row in sims.items():
        assert row["NPCName"] == "SameSaveName"
        assert row["SeedClassName"] == "Reaver"
        assert (row["SeedLevel"], row["SeedSkillLevel"]) == (7, 42.5)
        assert (row["SeedHairName"], row["SeedHairColor"], row["SeedSkinColor"]) == ("Hair_A", 2, 3)
        assert row["PrefabPath"] == f"Assets/Resources/{row['PrefabGuid']}.prefab"
        assert (row["IsGMCharacter"], row["Rival"]) == ((True, False) if "guid-a" in key else (False, True))
        assert [
            (entry["Position"], entry["ItemStableKey"])
            for entry in payload["equipment"]
            if entry["AuthoredSimStableKey"] == key
        ] == [(0, "item:a"), (1, None), (2, "item:a")]
    assert "is null" in payload["failures"][0]
    assert "no asset identity" in payload["failures"][1]
    assert "prefab asset" in payload["failures"][2]
    assert "lacks Character" in payload["failures"][3]
