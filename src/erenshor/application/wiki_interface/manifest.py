"""Immutable checkpoints for guarded MediaWiki interface deployment."""

from __future__ import annotations

import json
import os
import secrets
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path, PureWindowsPath
from typing import Literal, cast

from erenshor.infrastructure.wiki.client import MediaWikiPageRevision, MediaWikiPageSnapshot

DeployAction = Literal["unchanged", "created", "edited"]
MutationState = Literal["pending", "applied", "ambiguous"]
ContentModel = Literal["css", "javascript", "json", "vue", "wikitext"]
DeployRequestState = Literal["unattempted", "pending", "rejected"]

_ACTIONS = frozenset({"unchanged", "created", "edited"})
_MUTATION_STATES = frozenset({"pending", "applied", "ambiguous"})
_CONTENT_MODELS = frozenset({"css", "javascript", "json", "vue", "wikitext"})
_DEFINITION_TITLE = "MediaWiki:Gadgets-definition"
_DEFINITION_SOURCE = "wiki/gadgets/gadgets.toml"
_GADGET_TITLE_PREFIX = "MediaWiki:Gadget-"
_MODEL_BY_SUFFIX: dict[str, ContentModel] = {
    ".css": "css",
    ".js": "javascript",
    ".json": "json",
    ".vue": "vue",
}
_ENTRY_KEYS = frozenset(
    {
        "title",
        "source_path",
        "source_sha256",
        "content_model",
        "old_revision_id",
        "old_revision_timestamp",
        "new_revision_id",
        "rollback_text_source",
        "rollback_text_sha256",
        "deployed_text_sha256",
        "deploy_action",
        "mutation_state",
    }
)
_VERIFICATION_KEYS = frozenset({"edit_verification_error", "rollback_verification_error"})
_REQUEST_KEYS = frozenset(
    {
        "deploy_request_base",
        "deploy_account",
        "deploy_api_url",
        "rollback_request_base",
        "rollback_account",
        "rollback_api_url",
        "rollback_new_revision_id",
        "deploy_request_state",
        "rollback_request_state",
    }
)


@dataclass(frozen=True, slots=True)
class InterfaceEditVerificationReceipt:
    """Keep acknowledged native edit evidence without replacing the reviewed preimage."""

    new_revision_id: int
    written_snapshot: MediaWikiPageSnapshot | None = None
    actual_parent_snapshot: MediaWikiPageSnapshot | None = None


@dataclass(frozen=True, slots=True)
class InterfacePageManifestEntry:
    """One allowlisted interface page and its checkpointed deploy outcome."""

    title: str
    source_path: str
    source_sha256: str
    content_model: ContentModel
    old_revision_id: int | None = None
    old_revision_timestamp: str | None = None
    new_revision_id: int | None = None
    rollback_text_source: str | None = None
    rollback_text_sha256: str | None = None
    deployed_text_sha256: str | None = None
    deploy_action: DeployAction | None = None
    mutation_state: MutationState = "pending"
    edit_verification_error: InterfaceEditVerificationReceipt | None = None
    rollback_verification_error: InterfaceEditVerificationReceipt | None = None
    deploy_request_base: MediaWikiPageSnapshot | None = None
    deploy_account: str | None = None
    deploy_api_url: str | None = None
    deploy_request_state: DeployRequestState | None = None
    rollback_request_base: MediaWikiPageSnapshot | None = None
    rollback_account: str | None = None
    rollback_api_url: str | None = None
    rollback_request_state: Literal["pending", "rejected"] | None = None
    rollback_new_revision_id: int | None = None


@dataclass(frozen=True, slots=True)
class InterfaceDeployManifest:
    """Ordered immutable manifest used by deployment checkpoints and rollback."""

    entries: tuple[InterfacePageManifestEntry, ...]
    rollback_root: str | None = None

    def __post_init__(self) -> None:
        _validate_manifest(self)

    @property
    def action_counts(self) -> dict[DeployAction, int]:
        """Count completed actions, excluding unattempted checkpoint entries."""
        return {
            "unchanged": sum(entry.deploy_action == "unchanged" for entry in self.entries),
            "created": sum(entry.deploy_action == "created" for entry in self.entries),
            "edited": sum(entry.deploy_action == "edited" for entry in self.entries),
        }


def write_interface_deploy_manifest(manifest: InterfaceDeployManifest, path: Path) -> None:
    """Atomically write a strict, deterministic JSON manifest."""
    if not isinstance(manifest, InterfaceDeployManifest):
        raise TypeError("manifest must be an InterfaceDeployManifest")
    path = Path(path)
    if path.exists() and path.is_symlink():
        raise ValueError(f"manifest path must not be a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise ValueError(f"manifest parent must not be a symlink: {path.parent}")
    payload = {"entries": [asdict(entry) for entry in manifest.entries], "rollback_root": manifest.rollback_root}
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write(path, data)


def _atomic_write(path: Path, data: bytes) -> None:
    """Write bytes using a randomized exclusive temp file and durable replace."""
    temporary_path = path.with_name(f".{path.name}.{secrets.token_hex(16)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(temporary_path, flags | nofollow, 0o600)
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("manifest temporary write made no progress")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        temporary_path.replace(path)
        dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
        dir_fd = os.open(path.parent, dir_flags)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        with suppress(FileNotFoundError):
            temporary_path.unlink()


def read_interface_deploy_manifest(path: Path) -> InterfaceDeployManifest:
    """Read a manifest and reject unknown fields or malformed values."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid interface deploy manifest at {path}: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {"entries", "rollback_root"}:
        raise ValueError("interface deploy manifest must contain only entries and rollback_root")
    rollback_root = payload["rollback_root"]
    if rollback_root is not None and not isinstance(rollback_root, str):
        raise ValueError("interface deploy manifest rollback_root must be a string or null")
    raw_entries = payload["entries"]
    if not isinstance(raw_entries, list):
        raise ValueError("interface deploy manifest entries must be an array")
    entries = tuple(_entry_from_payload(raw, index) for index, raw in enumerate(raw_entries))
    manifest = InterfaceDeployManifest(entries=entries, rollback_root=rollback_root)
    return manifest


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate manifest field: {key}")
        result[key] = value
    return result


def _entry_from_payload(raw: object, index: int) -> InterfacePageManifestEntry:
    if not isinstance(raw, dict):
        raise ValueError(f"entries[{index}] must be an object")
    if not set(raw) >= _ENTRY_KEYS or set(raw) - _ENTRY_KEYS - _VERIFICATION_KEYS - _REQUEST_KEYS:
        missing = sorted(_ENTRY_KEYS - set(raw))
        unknown = sorted(set(raw) - _ENTRY_KEYS - _VERIFICATION_KEYS - _REQUEST_KEYS)
        details = ([f"missing {', '.join(missing)}"] if missing else []) + (
            [f"unknown {', '.join(unknown)}"] if unknown else []
        )
        raise ValueError(f"entries[{index}] has invalid fields ({'; '.join(details)})")
    title = _required_string(raw["title"], "title", index)
    source_path = _required_string(raw["source_path"], "source_path", index)
    source_sha256 = _required_string(raw["source_sha256"], "source_sha256", index)
    model = _required_string(raw["content_model"], "content_model", index)
    if model not in _CONTENT_MODELS:
        raise ValueError(f"entries[{index}].content_model is invalid")
    mutation_state_raw = raw["mutation_state"]
    if not isinstance(mutation_state_raw, str) or mutation_state_raw not in _MUTATION_STATES:
        raise ValueError(f"entries[{index}].mutation_state is invalid")
    action_raw = raw["deploy_action"]
    if action_raw is not None and (not isinstance(action_raw, str) or action_raw not in _ACTIONS):
        raise ValueError(f"entries[{index}].deploy_action is invalid")
    return InterfacePageManifestEntry(
        title=title,
        source_path=source_path,
        source_sha256=source_sha256,
        content_model=cast("ContentModel", model),
        old_revision_id=_optional_int(raw["old_revision_id"], "old_revision_id", index),
        old_revision_timestamp=_optional_string(raw["old_revision_timestamp"], "old_revision_timestamp", index),
        new_revision_id=_optional_int(raw["new_revision_id"], "new_revision_id", index),
        rollback_text_source=_optional_string(raw["rollback_text_source"], "rollback_text_source", index),
        rollback_text_sha256=_optional_digest(raw["rollback_text_sha256"], "rollback_text_sha256", index),
        deployed_text_sha256=_optional_digest(raw["deployed_text_sha256"], "deployed_text_sha256", index),
        deploy_action=cast("DeployAction | None", action_raw),
        mutation_state=cast("MutationState", mutation_state_raw),
        edit_verification_error=_verification_from_payload(raw.get("edit_verification_error"), index),
        rollback_verification_error=_verification_from_payload(raw.get("rollback_verification_error"), index),
        deploy_request_base=_snapshot_from_payload(raw.get("deploy_request_base"), index),
        deploy_account=_optional_string(raw.get("deploy_account"), "deploy_account", index),
        deploy_api_url=_optional_string(raw.get("deploy_api_url"), "deploy_api_url", index),
        deploy_request_state=cast(
            "DeployRequestState | None",
            _optional_string(raw.get("deploy_request_state"), "deploy_request_state", index),
        ),
        rollback_request_base=_snapshot_from_payload(raw.get("rollback_request_base"), index),
        rollback_account=_optional_string(raw.get("rollback_account"), "rollback_account", index),
        rollback_api_url=_optional_string(raw.get("rollback_api_url"), "rollback_api_url", index),
        rollback_request_state=cast(
            "Literal['pending', 'rejected'] | None",
            _optional_string(raw.get("rollback_request_state"), "rollback_request_state", index),
        ),
        rollback_new_revision_id=_optional_int(raw.get("rollback_new_revision_id"), "rollback_new_revision_id", index),
    )


def _verification_from_payload(raw: object, index: int) -> InterfaceEditVerificationReceipt | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {"new_revision_id", "written_snapshot", "actual_parent_snapshot"}:
        raise ValueError(f"entries[{index}] has invalid verification receipt fields")
    revision_id = _optional_int(raw["new_revision_id"], "verification.new_revision_id", index)
    if revision_id is None or revision_id <= 0:
        raise ValueError(f"entries[{index}] verification receipt lacks an acknowledged revision")
    return InterfaceEditVerificationReceipt(
        new_revision_id=revision_id,
        written_snapshot=_snapshot_from_payload(raw["written_snapshot"], index),
        actual_parent_snapshot=_snapshot_from_payload(raw["actual_parent_snapshot"], index),
    )


def _snapshot_from_payload(raw: object, index: int) -> MediaWikiPageSnapshot | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {
        "title",
        "source_text",
        "revision",
        "start_timestamp",
        "content_model",
    }:
        raise ValueError(f"entries[{index}] has invalid verification snapshot fields")
    revision_raw = raw["revision"]
    revision = None
    if revision_raw is not None:
        required_revision_fields = {
            "title",
            "page_id",
            "revision_id",
            "timestamp",
            "start_timestamp",
            "user",
            "parent_revision_id",
        }
        if (
            not isinstance(revision_raw, dict)
            or not set(revision_raw) >= required_revision_fields
            or set(revision_raw) - required_revision_fields - {"comment"}
        ):
            raise ValueError(f"entries[{index}] has invalid verification revision fields")
        page_id = _optional_int(revision_raw["page_id"], "verification.page_id", index)
        revision_id = _optional_int(revision_raw["revision_id"], "verification.revision_id", index)
        if page_id is None or revision_id is None:
            raise ValueError(f"entries[{index}] verification revision lacks IDs")
        comment = revision_raw.get("comment")
        if comment is not None and not isinstance(comment, str):
            raise ValueError(f"entries[{index}] has invalid verification revision comment")
        revision = MediaWikiPageRevision(
            title=_required_string(revision_raw["title"], "verification.title", index),
            page_id=page_id,
            revision_id=revision_id,
            timestamp=_required_string(revision_raw["timestamp"], "verification.timestamp", index),
            start_timestamp=_required_string(revision_raw["start_timestamp"], "verification.start_timestamp", index),
            user=_optional_string(revision_raw["user"], "verification.user", index),
            parent_revision_id=_optional_int(
                revision_raw["parent_revision_id"], "verification.parent_revision_id", index
            ),
            comment=comment,
        )
    return MediaWikiPageSnapshot(
        title=_required_string(raw["title"], "verification.title", index),
        source_text=_optional_string(raw["source_text"], "verification.source_text", index),
        revision=revision,
        start_timestamp=_required_string(raw["start_timestamp"], "verification.start_timestamp", index),
        content_model=_optional_string(raw["content_model"], "verification.content_model", index),
    )


def _required_string(value: object, name: str, index: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"entries[{index}].{name} must be a string")
    return value


def _optional_digest(value: object, name: str, index: int) -> str | None:
    if value is None:
        return None
    value = _required_string(value, name, index)
    if len(value) != 64:
        raise ValueError(f"entries[{index}].{name} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"entries[{index}].{name} must be hexadecimal") from error
    return value


def _optional_string(value: object, name: str, index: int) -> str | None:
    if value is None:
        return None
    return _required_string(value, name, index)


def _optional_int(value: object, name: str, index: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"entries[{index}].{name} must be an integer or null")
    return value


def _validate_manifest(manifest: InterfaceDeployManifest) -> None:
    seen: set[str] = set()
    if manifest.rollback_root is not None:
        _validate_relative_path(manifest.rollback_root, "rollback_root")
    for index, entry in enumerate(manifest.entries):
        if not isinstance(entry, InterfacePageManifestEntry):
            raise TypeError(f"entries[{index}] is not an InterfacePageManifestEntry")
        if not entry.title or entry.title in seen:
            raise ValueError(f"duplicate or empty interface page title: {entry.title!r}")
        seen.add(entry.title)
        if not entry.source_path:
            raise ValueError(f"entries[{index}].source_path must not be empty")
        _validate_relative_path(entry.source_path, f"entries[{index}].source_path")
        _validate_digest(entry.source_sha256, f"entries[{index}].source_sha256", index)
        if entry.content_model not in _CONTENT_MODELS:
            raise ValueError(f"entries[{index}].content_model is invalid")
        _validate_owned_page(entry, index)
        if entry.deploy_action is not None and entry.deploy_action not in _ACTIONS:
            raise ValueError(f"entries[{index}].deploy_action is invalid")
        if entry.mutation_state not in _MUTATION_STATES:
            raise ValueError(f"entries[{index}].mutation_state is invalid")
        if (entry.old_revision_id is None) != (entry.old_revision_timestamp is None):
            raise ValueError(f"entries[{index}] must record old revision ID and timestamp together")
        if entry.rollback_text_source is not None:
            _validate_relative_path(entry.rollback_text_source, f"entries[{index}].rollback_text_source")
        if entry.rollback_text_sha256 is not None:
            _validate_digest(entry.rollback_text_sha256, f"entries[{index}].rollback_text_sha256", index)
        if entry.deployed_text_sha256 is not None:
            _validate_digest(entry.deployed_text_sha256, f"entries[{index}].deployed_text_sha256", index)
        if entry.deploy_request_state not in (None, "unattempted", "pending", "rejected"):
            raise ValueError(f"entries[{index}] has invalid deploy request state")
        if entry.deploy_request_state == "rejected" and (
            entry.deploy_action is not None or entry.new_revision_id is not None or entry.mutation_state != "pending"
        ):
            raise ValueError(f"entries[{index}] rejected request must not record a completed mutation")
        if entry.rollback_request_state not in (None, "pending", "rejected"):
            raise ValueError(f"entries[{index}] has invalid rollback request state")
        if entry.rollback_request_state == "rejected" and entry.rollback_new_revision_id is not None:
            raise ValueError(f"entries[{index}] rejected rollback request must not have an acknowledgement")
        for request_base, account, api_url in (
            (entry.deploy_request_base, entry.deploy_account, entry.deploy_api_url),
            (entry.rollback_request_base, entry.rollback_account, entry.rollback_api_url),
        ):
            if (request_base is None) != (account is None) or (request_base is None) != (api_url is None):
                raise ValueError(f"entries[{index}] request base, account and API URL must be recorded together")
            if request_base is not None:
                _snapshot_from_payload(asdict(request_base), index)
                if (
                    request_base.title != entry.title
                    or not isinstance(account, str)
                    or not account.strip()
                    or not isinstance(api_url, str)
                    or not api_url.strip()
                ):
                    raise ValueError(f"entries[{index}] has invalid request identity")
        if entry.rollback_new_revision_id is not None and (
            type(entry.rollback_new_revision_id) is not int
            or entry.rollback_new_revision_id <= 0
            or entry.rollback_request_base is None
        ):
            raise ValueError(f"entries[{index}] has invalid rollback acknowledgement")
        for receipt in (entry.edit_verification_error, entry.rollback_verification_error):
            if receipt is not None:
                if not isinstance(receipt, InterfaceEditVerificationReceipt):
                    raise ValueError(f"entries[{index}] has invalid verification receipt")
                _verification_from_payload(asdict(receipt), index)
        if entry.edit_verification_error is not None:
            if entry.new_revision_id != entry.edit_verification_error.new_revision_id:
                raise ValueError(f"entries[{index}] verification receipt differs from acknowledged revision")
            if entry.mutation_state != "ambiguous":
                raise ValueError(f"entries[{index}] unverified edit must remain ambiguous")

        state = entry.mutation_state
        if state == "pending" and entry.deploy_action is not None:
            state = "applied"
        if state == "pending":
            if entry.deploy_action is not None or entry.new_revision_id is not None:
                raise ValueError(f"pending entry {entry.title} must not record a completed action")
        elif state == "applied":
            if entry.deploy_action is None:
                raise ValueError(f"applied entry {entry.title} lacks deploy action")
            if entry.deploy_action in ("created", "edited") and entry.new_revision_id is None:
                raise ValueError(f"applied entry {entry.title} lacks its deployed revision")
            if entry.deploy_action == "edited":
                if entry.old_revision_id is None or not entry.rollback_text_source:
                    raise ValueError(f"edited entry {entry.title} lacks revision or rollback sidecar")
                if entry.rollback_text_sha256 is None or entry.deployed_text_sha256 is None:
                    raise ValueError(f"edited entry {entry.title} lacks rollback or deployed text digest")
            elif entry.deploy_action == "created":
                if entry.deployed_text_sha256 is None:
                    raise ValueError(f"created entry {entry.title} lacks deployed text digest")
                if entry.old_revision_id is not None or entry.rollback_text_source is not None:
                    raise ValueError(f"created entry {entry.title} has prior-page rollback state")
            elif (
                entry.new_revision_id is not None
                or entry.old_revision_id is not None
                or entry.rollback_text_source is not None
            ):
                raise ValueError(f"unchanged entry {entry.title} has deploy state")
        else:  # ambiguous
            if entry.deploy_action not in ("created", "edited"):
                raise ValueError(f"ambiguous entry {entry.title} lacks a mutation action")
            if entry.deploy_action == "edited":
                if entry.old_revision_id is None or not entry.rollback_text_source:
                    raise ValueError(f"ambiguous edited entry {entry.title} lacks rollback state")
                if entry.rollback_text_sha256 is None or entry.deployed_text_sha256 is None:
                    raise ValueError(f"ambiguous edited entry {entry.title} lacks rollback or deployed text digest")
            else:
                if entry.deployed_text_sha256 is None:
                    raise ValueError(f"ambiguous created entry {entry.title} lacks deployed text digest")
                if entry.old_revision_id is not None or entry.rollback_text_source is not None:
                    raise ValueError(f"ambiguous created entry {entry.title} has prior-page rollback state")

    if sum(entry.title == _DEFINITION_TITLE for entry in manifest.entries) != 1:
        raise ValueError(f"interface deploy manifest must contain {_DEFINITION_TITLE} exactly once")


def _validate_digest(value: str, label: str, index: int) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"entries[{index}].{label.split('.')[-1]} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ValueError(f"entries[{index}].{label.split('.')[-1]} must be hexadecimal") from error


def _validate_owned_page(entry: InterfacePageManifestEntry, index: int) -> None:
    if entry.title == _DEFINITION_TITLE:
        if entry.source_path != _DEFINITION_SOURCE or entry.content_model != "wikitext":
            raise ValueError(f"entries[{index}] has invalid source or content model for {_DEFINITION_TITLE}")
        return
    if not entry.title.startswith(_GADGET_TITLE_PREFIX):
        raise ValueError(f"entries[{index}].title is not a repo-owned gadget page")
    source_path = Path(entry.source_path)
    try:
        relative_source = source_path.relative_to("wiki/gadgets")
    except ValueError as error:
        raise ValueError(f"entries[{index}].source_path is outside wiki/gadgets") from error
    expected_title = _GADGET_TITLE_PREFIX + relative_source.as_posix()
    expected_model = _MODEL_BY_SUFFIX.get(relative_source.suffix)
    if entry.title != expected_title or entry.content_model != expected_model:
        raise ValueError(f"entries[{index}] title, source path, and content model do not agree")


def _validate_relative_path(value: str, label: str) -> None:
    path = Path(value)
    windows_path = PureWindowsPath(value)
    if (
        "\\" in value
        or path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{label} must be a relative path without traversal")


def rollback_sidecar_filename(title: str) -> str:
    """Return a flat, injective percent-encoded sidecar filename."""
    from urllib.parse import quote

    if not title:
        raise ValueError("interface title must not be empty")
    return f"{quote(title, safe='')}.wiki"


__all__ = [
    "ContentModel",
    "DeployAction",
    "InterfaceDeployManifest",
    "InterfaceEditVerificationReceipt",
    "InterfacePageManifestEntry",
    "MutationState",
    "read_interface_deploy_manifest",
    "rollback_sidecar_filename",
    "write_interface_deploy_manifest",
]
