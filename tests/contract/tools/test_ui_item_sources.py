"""Exercise native UI references through the production Unity export listener."""

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
_PROJECT = Path(__file__).resolve().parents[2] / "fixtures" / "ui_item_sources"


def test_native_ui_sources_preserve_serialized_identity_and_access(
    tmp_path: Path, dotnet_build: Callable[..., None]
) -> None:
    out = tmp_path / "build"
    dotnet_build(_PROJECT, "-o", str(out), f"-p:BaseIntermediateOutputPath={tmp_path / 'obj'}/")
    result = subprocess.run(
        ["dotnet", str(out / "UiItemSourcesFixture.dll")], capture_output=True, text=True, check=True
    )
    payload = json.loads(result.stdout)
    forward = {row["ComponentType"]: row for row in payload["forward"]}
    assert payload["unrelated"] == []
    reverse = {row["ComponentType"]: row for row in payload["reverse"]}
    assert forward == reverse
    assert set(forward) == {"ReplenishTMOGHide", "PlanningTableUI"}

    hide = forward["ReplenishTMOGHide"]
    assert hide["StableKey"] == "ui:loadscene:ui[0]/hide[0]:replenishtmoghide:0"
    assert hide["ObjectKey"] == "object:loadscene:ui[0]/hide[0]"
    assert hide["Scene"] == "LoadScene"
    assert hide["HierarchyPath"] == "UI[0]/Hide[0]"
    assert hide["IconHierarchyPath"] == hide["HierarchyPath"]
    assert hide["Slot"] == "MyIcon"
    assert hide["SerializedItemStableKey"] == "item:native serialized seed"
    assert hide["SerializedQuantity"] == 7
    assert hide["ReplenishItemStableKey"] == "item:native replenishment gift"
    assert hide["ReplenishSourceKey"] == "ui:loadscene:manager[0]:misc:0"

    portal = forward["PlanningTableUI"]
    assert portal["ObjectKey"] == "object:loadscene:ui[0]/planning[1]"
    assert portal["Slot"] == "Portal"
    assert portal["IconHierarchyPath"] == "UI[0]/Planning[1]/Portal[0]"
    assert portal["SerializedItemStableKey"] == "item:native portal gift"
    assert portal["SerializedQuantity"] == 3
    assert portal["ReplenishItemStableKey"] is None
    assert portal["ReplenishSourceKey"] is None
    assert portal["NotInInventory"] is True
    assert portal["DisplayOnly"] is True
    assert portal["PlayerOwned"] is True
    empty_portal = next(row for row in payload["empty"] if row["ComponentType"] == "PlanningTableUI")
    assert empty_portal["SerializedItemStableKey"] is None
    assert empty_portal["ReplenishItemStableKey"] is None

    access = payload["access"]
    targets = {row["StableKey"]: row for row in access["targets"]}
    assert len(targets) == 2
    hierarchy = {row["ObjectKey"]: row for row in access["hierarchy"]}
    assert len(hierarchy) == 4
    desk = next(row for row in targets.values() if row["HierarchyPath"] == "Rooms[0]/Desk[0]")
    assert desk["Scene"] == "Reliquary"
    assert desk["HierarchyPath"] == "Rooms[0]/Desk[0]"
    assert desk["Tag"] == "PlanningDesk"
    assert desk["ActiveSelf"] is True
    assert desk["ActiveInHierarchy"] is False
    assert (desk["X"], desk["Y"], desk["Z"]) == (11, 12, 13)
    assert desk["ObjectKey"] == "object:reliquary:rooms[0]/desk[0]"
    parent = hierarchy[desk["ObjectKey"]]["ParentObjectKey"]
    assert parent == "object:reliquary:rooms[0]"
    assert hierarchy[parent]["ParentObjectKey"] is None
    assert hierarchy[parent]["ActiveSelf"] is False
    blocked = next(row for row in targets.values() if "BlockedDesk" in row["HierarchyPath"])
    assert blocked["ActiveSelf"] is True
    assert blocked["ActiveInHierarchy"] is False
    disabled = hierarchy[blocked["ObjectKey"]]["ParentObjectKey"]
    assert hierarchy[disabled]["ActiveSelf"] is False
    assert hierarchy[disabled]["ParentObjectKey"] == parent
    assert {row["Scene"] for row in hierarchy.values()} == {"Reliquary"}
    assert all(row["IsSceneObject"] for row in hierarchy.values())

    failures = payload["failures"]
    assert failures["missing_icon"].endswith("has no MyIcon icon")
    assert failures["missing_misc"].endswith("needs exactly one native Misc.TMOGHIDE reference in LoadScene")
    assert failures["ambiguous_misc"] == failures["missing_misc"]
