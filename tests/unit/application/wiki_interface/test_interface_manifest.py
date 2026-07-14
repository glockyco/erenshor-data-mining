from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from erenshor.application.wiki_interface.manifest import (
    InterfaceDeployManifest,
    InterfacePageManifestEntry,
    MutationState,
    read_interface_deploy_manifest,
    rollback_sidecar_filename,
    write_interface_deploy_manifest,
)


def _entry(
    title: str = "MediaWiki:Gadget-first.css",
    *,
    state: MutationState = "pending",
    action: str | None = None,
    old: bool = False,
    new: bool = False,
    sidecar: bool = False,
) -> InterfacePageManifestEntry:
    return InterfacePageManifestEntry(
        title=title,
        source_path="wiki/gadgets/first.css"
        if title != "MediaWiki:Gadgets-definition"
        else "wiki/gadgets/gadgets.toml",
        source_sha256="a" * 64,
        content_model="css" if title != "MediaWiki:Gadgets-definition" else "wikitext",
        old_revision_id=1 if old else None,
        old_revision_timestamp="2026-07-13T00:00:00Z" if old else None,
        new_revision_id=2 if new else None,
        rollback_text_source="rollback/MediaWiki%3AGadget-first.css.wiki" if sidecar else None,
        rollback_text_sha256="b" * 64 if sidecar else None,
        deployed_text_sha256="c" * 64 if new else None,
        deploy_action=action,
        mutation_state=state,
    )


def _manifest(entry: InterfacePageManifestEntry) -> InterfaceDeployManifest:
    definition = _entry("MediaWiki:Gadgets-definition", state="applied", action="unchanged")
    return InterfaceDeployManifest((entry, definition), rollback_root="rollback")


def test_manifest_round_trip_preserves_root_digests_and_mutation_state(tmp_path: Path) -> None:
    manifest = _manifest(_entry(state="applied", action="edited", old=True, new=True, sidecar=True))
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    assert read_interface_deploy_manifest(path) == manifest
    assert json.loads(path.read_text(encoding="utf-8"))["rollback_root"] == "rollback"


def test_manifest_parser_rejects_missing_or_unknown_schema_fields(tmp_path: Path) -> None:
    manifest = _manifest(_entry())
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("rollback_root")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="entries and rollback_root"):
        read_interface_deploy_manifest(path)

    payload = {"entries": json.loads(json.dumps(payload.get("entries", []))), "rollback_root": "rollback", "extra": 1}
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="entries and rollback_root"):
        read_interface_deploy_manifest(path)


@pytest.mark.parametrize(
    ("operation", "message"),
    [("missing", "missing mutation_state"), ("unknown", "unknown unexpected")],
)
def test_manifest_parser_rejects_missing_or_unknown_entry_fields(tmp_path: Path, operation: str, message: str) -> None:
    manifest = _manifest(_entry())
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if operation == "missing":
        payload["entries"][0].pop("mutation_state")
    else:
        payload["entries"][0]["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        read_interface_deploy_manifest(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rollback_root", 3, "rollback_root must be a string or null"),
        ("rollback_root", "../rollback", "relative path"),
        ("rollback_text_sha256", "not-a-digest", "rollback_text_sha256 must be a SHA-256 digest"),
        ("deployed_text_sha256", "not-a-digest", "deployed_text_sha256 must be a SHA-256 digest"),
        ("mutation_state", "unknown", "mutation_state is invalid"),
    ],
)
def test_manifest_parser_rejects_invalid_root_digests_and_mutation_state(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    manifest = _manifest(_entry(state="applied", action="edited", old=True, new=True, sidecar=True))
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if field == "rollback_root":
        payload[field] = value
    else:
        payload["entries"][0][field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        read_interface_deploy_manifest(path)


@pytest.mark.parametrize(
    ("state", "action", "field", "message"),
    [
        ("applied", "edited", "rollback_text_sha256", "rollback or deployed text digest"),
        ("applied", "edited", "deployed_text_sha256", "rollback or deployed text digest"),
        ("ambiguous", "edited", "rollback_text_sha256", "rollback or deployed text digest"),
        ("ambiguous", "edited", "deployed_text_sha256", "rollback or deployed text digest"),
        ("applied", "created", "deployed_text_sha256", "deployed text digest"),
        ("ambiguous", "created", "deployed_text_sha256", "deployed text digest"),
    ],
)
def test_manifest_rejects_missing_deployed_or_rollback_digest_for_mutation_state(
    state: MutationState, action: str, field: str, message: str
) -> None:
    edited = action == "edited"
    entry = replace(
        _entry(state=state, action=action, old=edited, new=True, sidecar=edited),
        **{field: None},
    )
    with pytest.raises(ValueError, match=message):
        _manifest(entry)


def test_manifest_parser_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"entries": [], "entries": [], "rollback_root": "rollback"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate manifest field"):
        read_interface_deploy_manifest(path)


def test_sidecar_filename_is_flat_and_injective() -> None:
    first = rollback_sidecar_filename("MediaWiki:Gadget-a.css")
    second = rollback_sidecar_filename("MediaWiki:Gadget/a.css")
    assert first != second
    assert "/" not in first
    assert "/" not in second
