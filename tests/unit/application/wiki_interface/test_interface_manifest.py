from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from erenshor.application.wiki_interface.manifest import (
    InterfaceDeployManifest,
    InterfaceEditVerificationReceipt,
    InterfacePageManifestEntry,
    MutationState,
    read_interface_deploy_manifest,
    rollback_sidecar_filename,
    write_interface_deploy_manifest,
)
from erenshor.infrastructure.wiki.client import MediaWikiPageRevision, MediaWikiPageSnapshot


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


def test_manifest_reads_pre_verification_receipt_manifests(tmp_path: Path) -> None:
    manifest = _manifest(_entry(state="applied", action="edited", old=True, new=True, sidecar=True))
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload["entries"]:
        entry.pop("edit_verification_error")
        entry.pop("rollback_verification_error")
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert read_interface_deploy_manifest(path) == manifest


@pytest.mark.parametrize("revision_id", [None, True, 0, -1, "2"])
def test_manifest_parser_rejects_verification_receipt_without_valid_ack(tmp_path: Path, revision_id: object) -> None:
    entry = replace(
        _entry(state="ambiguous", action="edited", old=True, new=True, sidecar=True),
        edit_verification_error=InterfaceEditVerificationReceipt(new_revision_id=2),
    )
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(_manifest(entry), path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"][0]["edit_verification_error"]["new_revision_id"] = revision_id
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=r"verification.*(revision|integer)"):
        read_interface_deploy_manifest(path)


def test_manifest_verification_receipt_cannot_appear_as_applied() -> None:
    entry = replace(
        _entry(state="applied", action="edited", old=True, new=True, sidecar=True),
        edit_verification_error=InterfaceEditVerificationReceipt(new_revision_id=2),
    )
    with pytest.raises(ValueError, match="unverified edit must remain ambiguous"):
        _manifest(entry)


@pytest.mark.parametrize("comment", [None, "", "Reviewed marker sha256:actual"])
def test_manifest_round_trip_preserves_native_request_identity_and_rollback_ack(
    tmp_path: Path, comment: str | None
) -> None:
    title = "MediaWiki:Gadget-first.css"
    base = MediaWikiPageSnapshot(
        title=title,
        source_text="old\r\ntext\u00a0",
        revision=MediaWikiPageRevision(
            title=title,
            page_id=10,
            revision_id=1,
            timestamp="2026-07-13T00:00:00Z",
            start_timestamp="2026-07-13T00:00:01Z",
            user="Editor",
            parent_revision_id=0,
            comment=comment,
        ),
        start_timestamp="2026-07-13T00:00:01Z",
        content_model="css",
    )
    assert base.revision is not None
    rollback_base = replace(base, revision=replace(base.revision, revision_id=2, parent_revision_id=1))
    entry = replace(
        _entry(state="applied", action="edited", old=True, new=True, sidecar=True),
        deploy_request_base=base,
        deploy_account="InterfaceAdmin",
        deploy_api_url="https://fixture.invalid/api.php",
        rollback_request_base=rollback_base,
        rollback_account="InterfaceAdmin",
        rollback_api_url="https://fixture.invalid/api.php",
        rollback_new_revision_id=3,
    )
    manifest = _manifest(entry)
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    assert read_interface_deploy_manifest(path) == manifest
    restored_base = read_interface_deploy_manifest(path).entries[0].deploy_request_base
    assert restored_base is not None
    assert restored_base.source_text == "old\r\ntext\u00a0"
    assert restored_base.revision is not None
    assert restored_base.revision.comment == comment
    if comment is None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for key in ("deploy_request_base", "rollback_request_base"):
            payload["entries"][0][key]["revision"].pop("comment")
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert read_interface_deploy_manifest(path) == manifest


@pytest.mark.parametrize(
    "field", ["deploy_account", "deploy_api_url", "rollback_account", "rollback_api_url", "rollback_new_revision_id"]
)
def test_manifest_rejects_request_identity_without_a_request_base(field: str) -> None:
    value = 3 if field == "rollback_new_revision_id" else "InterfaceAdmin"
    entry = replace(_entry(), **{field: value})
    with pytest.raises(ValueError, match=r"request base|rollback acknowledgement"):
        _manifest(entry)


def test_manifest_reads_manifests_without_request_attribution_fields(tmp_path: Path) -> None:
    manifest = _manifest(_entry(state="applied", action="edited", old=True, new=True, sidecar=True))
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload["entries"]:
        for field in (
            "deploy_request_base",
            "deploy_account",
            "deploy_api_url",
            "deploy_request_state",
            "rollback_request_base",
            "rollback_account",
            "rollback_api_url",
            "rollback_request_state",
            "rollback_new_revision_id",
        ):
            entry.pop(field)
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert read_interface_deploy_manifest(path) == manifest


@pytest.mark.parametrize("state", ["unattempted", "pending", "rejected"])
def test_manifest_round_trip_preserves_request_lifecycle(tmp_path: Path, state: str) -> None:
    manifest = _manifest(replace(_entry(), deploy_request_state=state))
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    assert read_interface_deploy_manifest(path) == manifest


def test_manifest_rejects_unknown_request_lifecycle(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(_manifest(_entry()), path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"][0]["deploy_request_state"] = "settled"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid deploy request state"):
        read_interface_deploy_manifest(path)


@pytest.mark.parametrize("state", ["pending", "rejected"])
def test_manifest_round_trip_preserves_rollback_request_lifecycle(tmp_path: Path, state: str) -> None:
    manifest = _manifest(replace(_entry(), rollback_request_state=state))
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    assert read_interface_deploy_manifest(path) == manifest


@pytest.mark.parametrize("comment", [False, 7, [], {}])
def test_manifest_rejects_nontext_revision_comments(tmp_path: Path, comment: object) -> None:
    title = "MediaWiki:Gadget-first.css"
    base = MediaWikiPageSnapshot(
        title,
        "old source",
        MediaWikiPageRevision(title, 10, 1, "t", "s", "Editor", parent_revision_id=0),
        "s",
        "css",
    )
    manifest = _manifest(
        replace(
            _entry(state="applied", action="edited", old=True, new=True, sidecar=True),
            deploy_request_base=base,
            deploy_account="InterfaceAdmin",
            deploy_api_url="https://fixture.invalid/api.php",
        )
    )
    path = tmp_path / "manifest.json"
    write_interface_deploy_manifest(manifest, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"][0]["deploy_request_base"]["revision"]["comment"] = comment
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="revision comment"):
        read_interface_deploy_manifest(path)
