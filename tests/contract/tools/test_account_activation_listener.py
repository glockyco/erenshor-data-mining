"""Execute production activation capture without running game lifecycle or account state."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

pytestmark = pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet SDK not installed")
_ROOT = Path(__file__).resolve().parents[3]
_PROJECT = _ROOT / "tests" / "fixtures" / "account_activation"
_CATALOG = _ROOT / "src/Assets/Editor/ExportSystem/AssetScanner/dynamic-spawn-catalog.toml"


def _assert_complete_catalog(payload: dict[str, Any]) -> None:
    catalog = tomllib.loads(_CATALOG.read_text())
    expected = {entry["script"]: entry for entry in catalog["activation"]}
    runtime = payload["allRules"]
    assert {entry["Script"]: entry["Rule"] for entry in runtime["catalog"]} == {
        name: entry["rule"] for name, entry in expected.items()
    }
    rows = runtime["rows"]
    sources = {row["Script"]: row for row in rows["sources"]}
    assert set(sources) == set(expected)
    references = rows["references"]
    assert len({row["ReferenceId"] for row in references}) == len(references)
    targets = rows["targets"]
    assert len({row["TargetId"] for row in targets}) == len(targets)
    assert {row["ReferenceId"] for row in targets} <= {row["ReferenceId"] for row in references}
    for name, entry in expected.items():
        source = sources[name]
        assert source["RuleId"] == entry["rule"]
        assert source["ComponentIsEnabled"] is True
        assert source["IsEnabled"] is True
        configured = [row for row in references if row["SourceKey"] == source["SourceKey"]]
        fields = {row["Field"] for row in configured}
        synthetic = {"$host", "$host_spawn_point"} if name == "ReliqDisableFiendSpawn" else {"$host"}
        if name == "ReliqPortalListener":
            synthetic.add("$portal_active_self")
        if name == "AstraListener":
            synthetic.add("Dragon")
        if name == "StowawayPortal":
            synthetic.update({"$checkin_character", "$checkin_spawn_point"})
        assert fields == set(entry["fields"]) | synthetic
        for reference in configured:
            assert reference["ReferenceId"] == (
                f"{source['SourceKey']}:field:{reference['Field']}:{reference['ReferenceIndex']}"
            )
            assert reference["ReferenceKind"] not in {"null", "empty_collection"}
        host = next(row for row in configured if row["Field"] == "$host")
        assert source["ObjectKey"] == host["ReferenceKey"]
        for field in entry["fields"]:
            indexes = [row["ReferenceIndex"] for row in configured if row["Field"] == field]
            assert indexes in ([0], [0, 1])
    assert {row["ReferenceKind"] for row in references} == {
        "object",
        "character",
        "spawn_point",
        "zone_line",
        "item",
        "quest",
        "bool",
        "controller",
        "string",
    }
    # A controller reference is the referenced controller's own source key.
    vision = next(row for row in references if row["Field"] == "Vision")
    assert vision["ReferenceKey"] == sources["SivTorchLight"]["SourceKey"]
    assert next(row for row in references if row["Field"] == "IDtoActivate")["ReferenceKey"] == "38656873"
    boolean = next(row for row in references if row["Field"] == "UseEssentialSpawnsToBlockThisInstance")
    assert boolean["ReferenceKind"] == "bool"
    assert boolean["BoolValue"] is False
    assert boolean["ReferenceKey"] is None
    assert next(row for row in references if row["Field"] == "RequiredInInventory")["ReferenceKey"] == (
        "item:fixture:required"
    )
    assert next(row for row in references if row["Field"] == "RequiredQuest")["ReferenceKey"] == (
        "quest:fixture:required"
    )
    assert next(row for row in references if row["Field"] == "ward1")["ReferenceKey"] == ("character:fixture:ward")
    astra = {row["Field"]: row for row in references if row["SourceKey"] == sources["AstraListener"]["SourceKey"]}
    assert (astra["StarSpawns"]["ReferenceKind"], astra["StarSpawns"]["ReferenceKey"]) == (
        "spawn_point",
        "spawn:fixture:configured-target",
    )
    assert (astra["Dragon"]["ReferenceKind"], astra["Dragon"]["ReferenceKey"]) == (
        "character",
        "character:fixture:ward",
    )
    stowaway = {row["Field"]: row for row in references if row["SourceKey"] == sources["StowawayPortal"]["SourceKey"]}
    assert (stowaway["KeeperSpawn"]["ReferenceKind"], stowaway["KeeperSpawn"]["ReferenceKey"]) == (
        "object",
        "object:reliquary:configured-target[0]",
    )
    assert (stowaway["$checkin_character"]["ReferenceKind"], stowaway["$checkin_character"]["ReferenceKey"]) == (
        "character",
        "character:fixture:ward",
    )
    assert (
        stowaway["$checkin_spawn_point"]["ReferenceKind"],
        stowaway["$checkin_spawn_point"]["ReferenceKey"],
    ) == ("spawn_point", "spawn:fixture:configured-target")
    assert stowaway["$checkin_character"]["ReferenceIndex"] == stowaway["$checkin_spawn_point"]["ReferenceIndex"] == 0
    assert [
        row
        for row in references
        if row["SourceKey"] == sources["StowawayPortal"]["SourceKey"] and row["Field"] == "$checkin_character"
    ] == [stowaway["$checkin_character"]]
    enabled_objects = [
        row
        for row in targets
        if row["ReferenceId"] == stowaway["KeeperSpawn"]["ReferenceId"]
        and row["ResolutionMode"] == "enable"
        and row["Kind"] == "object"
    ]
    assert len(enabled_objects) == 1
    assert enabled_objects[0]["ObjectKey"] == stowaway["KeeperSpawn"]["ReferenceKey"]


def _assert_account_bindings(case: dict[str, Any]) -> None:
    assert case["writesBeforeFinish"] == 0
    assert case["exactHostSpawnRequests"] is True
    rows = case["rows"]
    assert len(rows["sources"]) == 2
    assert len(rows["references"]) == 4
    assert len(rows["targets"]) == 8
    assert rows["operations"] == [
        "create:ScriptedActivatorRecord",
        "create:ScriptedActivatorReferenceRecord",
        "create:ScriptedActivatorTargetRecord",
        "transaction",
        "delete:ScriptedActivatorTargetRecord",
        "delete:ScriptedActivatorReferenceRecord",
        "delete:ScriptedActivatorRecord",
        "insert:ScriptedActivatorRecord",
        "insert:ScriptedActivatorReferenceRecord",
        "insert:ScriptedActivatorTargetRecord",
    ]
    sources = {row["SourceKey"]: row for row in rows["sources"]}
    for index, fixture in enumerate(case["input"]):
        source_key = f"{fixture['objectKey']}:script:ReliqDisableFiendSpawn:0"
        source = sources[source_key]
        assert source["RuleId"] == "reliquary_account_claim"
        assert source["Script"] == "ReliqDisableFiendSpawn"
        assert source["ObjectKey"] == fixture["objectKey"]
        assert source["SourceScene"] == "Reliquary"
        assert source["SourceObjectName"] == "Spawn Point"
        assert (source["X"], source["Y"], source["Z"]) == (11 + index, 22, 33)
        assert source["HostCharacterStableKey"] is None
        assert source["ComponentIsEnabled"] is fixture["componentEnabled"] is (index == 0)
        assert source["IsEnabled"] is fixture["effectiveActive"] is (index == 0 and case["activity"] == "active")
        assert fixture["spawnComponentEnabled"] is True
        assert fixture["spawnCanSpawn"] is (index == 0)
        assert fixture["spawnEffectiveActive"] is (case["activity"] == "active")
        assert fixture["hostActiveSelf"] is (case["activity"] != "inactive_self")
        assert fixture["hostActiveInHierarchy"] is (case["activity"] == "active")
        references = {row["Field"]: row for row in rows["references"] if row["SourceKey"] == source_key}
        assert set(references) == {"$host", "$host_spawn_point"}
        for field, kind, key in (
            ("$host", "object", fixture["objectKey"]),
            ("$host_spawn_point", "spawn_point", fixture["spawnKey"]),
        ):
            reference = references[field]
            reference_id = f"{source_key}:field:{field}:0"
            assert reference == {
                "ReferenceId": reference_id,
                "SourceKey": source_key,
                "Field": field,
                "ReferenceIndex": 0,
                "ReferenceKind": kind,
                "ReferenceKey": key,
                "BoolValue": None,
            }
            targets = [row for row in rows["targets"] if row["ReferenceId"] == reference_id]
            assert {(row["Kind"], row["Key"]) for row in targets} == {
                ("object", fixture["objectKey"]),
                ("spawn_point", fixture["spawnKey"]),
            }
            for target in targets:
                assert target["TargetId"] == f"{reference_id}:reference:{target['Kind']}:{target['Key']}"
                assert target["ResolutionMode"] == "reference"
                assert target["Scene"] == "Reliquary"
                assert target["ObjectKey"] == fixture["objectKey"]
                assert target["ObjectName"] == "Spawn Point"
                assert target["IsEnabled"] is fixture["spawnEffectiveActive"]
    assert case["resolveRequests"] == [
        {"objectKey": fixture["objectKey"], "enabling": False} for fixture in case["input"] for _ in range(2)
    ]


def test_account_activation_captures_disabled_awake_host_binding(
    tmp_path: Path, dotnet_build: Callable[..., None]
) -> None:
    out = tmp_path / "build"
    dotnet_build(_PROJECT, "-o", str(out), f"-p:BaseIntermediateOutputPath={tmp_path / 'obj'}/")
    result = subprocess.run(
        ["dotnet", str(out / "AccountActivationFixture.dll"), str(_CATALOG)],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    _assert_complete_catalog(payload)
    _assert_unknown_candidates(payload["unknownCandidates"])
    assert {case["activity"] for case in payload["accounts"]} == {"active", "inactive_self", "inactive_parent"}
    for case in payload["accounts"]:
        _assert_account_bindings(case)
    missing = payload["missing"]
    assert missing["error"] == ("Reliquary account suppressor requires a host SpawnPoint: " + missing["sourceKey"])
    assert missing["spawnRequests"] == 0  # A different host's SpawnPoint cannot satisfy GetComponent.
    assert missing["rows"] == {"sources": [], "references": [], "targets": [], "operations": []}
    for case in payload["portals"]:
        assert case["error"] is None
        assert case["portalActiveSelf"] is (case["activity"] != "inactive_self")
        assert case["portalActiveInHierarchy"] is (case["activity"] == "active")
        references = {row["Field"]: row for row in case["rows"]["references"]}
        scalar = references["$portal_active_self"]
        assert scalar["ReferenceKind"] == "bool"
        assert scalar["BoolValue"] is case["portalActiveSelf"]
        assert scalar["ReferenceKey"] is None
        assert references["ReliqZL"]["ReferenceKind"] == "zone_line"
        assert references["ReliqZL"]["ReferenceKey"] == "zoneline:fixture:stored-return"
        assert references["ReliqPort"]["ReferenceKind"] == "object"
        assert references["ReliqPort"]["ReferenceKey"] == case["portalKey"]
        line_reference = references["ReliqZL"]["ReferenceId"]
        assert any(
            row["ReferenceId"] == line_reference and row["Kind"] == "zone_line" and row["Key"] == case["lineKey"]
            for row in case["rows"]["targets"]
        )
    for case in payload["missingPortalBindings"]:
        assert case["error"] is not None
        assert "Missing configured activation reference" in case["error"]
        assert case["rows"] == {"sources": [], "references": [], "targets": [], "operations": []}


def _assert_unknown_candidates(payload: dict[str, Any]) -> None:
    candidates = {row["field"]: row for row in payload["candidates"]}
    expected: dict[str, tuple[bool, str | None]] = {
        "PrivateActor": (True, "character:foreign"),
        "PrivateActorGroup": (True, "character:foreign"),
        "RuntimeActor": (False, None),
        "NonSerializedActor": (False, None),
        "ReadonlyActor": (False, None),
        "StaticActor": (False, None),
        "SelfComponent": (True, None),
        "UnrelatedComponent": (True, None),
        "ComponentLinks": (True, None),
        "ActorReferences": (True, "character:foreign"),
    }
    assert candidates.keys() == expected.keys()
    for name, (serialized, actor) in expected.items():
        assert candidates[name] == {"field": name, "serialized": serialized, "actor": actor}
    cache = payload["selfCache"]
    assert cache["serialized"] is True
    assert cache["classification"] == "Denied"
    assert cache["actualHost"] is True
    assert cache["foreignCacheError"].startswith("Host character cache does not reference its own Character:")
    assert cache["missingHostError"].startswith("Host character cache does not reference its own Character:")
