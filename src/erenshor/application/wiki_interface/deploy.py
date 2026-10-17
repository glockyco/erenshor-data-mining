"""Guarded deployment and rollback for repository-owned MediaWiki gadgets."""

from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import Callable, Collection, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol

from erenshor.application.wiki_interface.gadgets import (
    gadget_source_pages,
    load_gadget_spec,
    reconcile_definition,
)
from erenshor.application.wiki_interface.manifest import (
    ContentModel,
    DeployAction,
    InterfaceDeployManifest,
    InterfaceEditVerificationReceipt,
    InterfacePageManifestEntry,
    rollback_sidecar_filename,
)
from erenshor.infrastructure.wiki.client import (
    MediaWikiAssertionError,
    MediaWikiEditConflictError,
    MediaWikiEditVerificationError,
    MediaWikiPageRevision,
    MediaWikiPageSnapshot,
    MediaWikiPermissionError,
)
from erenshor.infrastructure.wiki.content import normalize_saved_text

DEFINITION_TITLE = "MediaWiki:Gadgets-definition"


class InterfaceDeployError(ValueError):
    """Base class for fail-closed interface deployment errors."""


class InterfacePermissionError(PermissionError, InterfaceDeployError):
    """The authenticated user cannot edit the MediaWiki interface namespace."""


class InterfaceRevisionConflictError(InterfaceDeployError):
    """A page changed after the deployment revision recorded in the manifest."""


class InterfaceSourceDriftError(InterfaceDeployError):
    """A local source changed after planning and before mutation."""


class InterfaceMutationError(InterfaceDeployError):
    """A remote mutation may have committed but could not be durably checkpointed."""

    def __init__(self, message: str, manifest: InterfaceDeployManifest) -> None:
        super().__init__(message)
        self.manifest = manifest


class InterfaceDeployClient(Protocol):
    """The narrow MediaWiki API needed by this deployment path."""

    api_url: str

    @property
    def edit_account(self) -> str: ...

    def get_current_user_rights(
        self,
        assertion: Literal["user"] = "user",
        assert_user: str | None = None,
    ) -> Collection[str]: ...

    def get_page_snapshots(
        self,
        titles: Sequence[str],
        assertion: Literal["user"] = "user",
        assert_user: str | None = None,
    ) -> Mapping[str, MediaWikiPageSnapshot]: ...

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = False,
        assertion: Literal["user"] = "user",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int: ...

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = False,
        assertion: Literal["user"] = "user",
        assert_user: str | None = None,
        content_model: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class InterfaceDeployPlanEntry:
    """Immutable planned action with exact upload text and snapshot guard."""

    title: str
    source_path: str
    source_sha256: str
    content_model: ContentModel
    planned_action: DeployAction
    new_text: str
    snapshot: MediaWikiPageSnapshot


@dataclass(frozen=True, slots=True)
class InterfaceDeployPlan:
    """Preflight plan, including the exact snapshots used as write guards."""

    entries: tuple[InterfaceDeployPlanEntry, ...]
    assert_user: str | None = None

    @property
    def action_counts(self) -> dict[DeployAction, int]:
        return {
            "unchanged": sum(entry.planned_action == "unchanged" for entry in self.entries),
            "created": sum(entry.planned_action == "created" for entry in self.entries),
            "edited": sum(entry.planned_action == "edited" for entry in self.entries),
        }


@dataclass(frozen=True, slots=True)
class InterfaceDeployResult:
    """Final checkpoint manifest for a successful deployment."""

    manifest: InterfaceDeployManifest


@dataclass(frozen=True, slots=True)
class InterfaceRollbackEntry:
    title: str
    restored_revision_id: int | None
    new_revision_id: int


@dataclass(frozen=True, slots=True)
class InterfaceRollbackResult:
    entries: tuple[InterfaceRollbackEntry, ...]
    created_titles: tuple[str, ...] = ()

    @property
    def restored_titles(self) -> tuple[str, ...]:
        return tuple(entry.title for entry in self.entries)


Checkpoint = Callable[[InterfaceDeployManifest], None]


def plan_interface_pages(
    repo_root: Path,
    client: InterfaceDeployClient,
    assert_user: str | None = None,
) -> InterfaceDeployPlan:
    """Snapshot every allowlisted source and registration page in one batch.

    The deploy writes in plan order: new gadget pages, then the definition,
    then the changed pages. So a new gadget's page exists before the definition
    registers it, and the definition registers it before a page that loads it
    changes, and no reader gets a gadget that asks for an unknown module.
    """
    root = repo_root.resolve()
    spec = load_gadget_spec(root)
    source_pages = gadget_source_pages(spec, root)
    definition_path = root / "wiki" / "gadgets" / "gadgets.toml"
    definition_hash = hashlib.sha256(definition_path.read_bytes()).hexdigest()
    titles = [page.title for page in source_pages] + [DEFINITION_TITLE]
    snapshots = client.get_page_snapshots(titles, assertion="user", assert_user=assert_user)
    missing = [title for title in titles if title not in snapshots]
    if missing:
        raise InterfaceDeployError(f"Missing page snapshots for: {', '.join(missing)}")

    entries: list[InterfaceDeployPlanEntry] = []
    for page in source_pages:
        source_bytes = (root / page.source_path).read_bytes()
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        source_text = _decode_source(page.title, source_bytes)
        snapshot = snapshots[page.title]
        remote_text = _snapshot_text(snapshot)
        revision = _snapshot_revision(snapshot)
        if remote_text is None:
            action: DeployAction = "created"
        elif normalize_saved_text(remote_text) == normalize_saved_text(source_text):
            action = "unchanged"
        elif revision is None:
            raise InterfaceDeployError(f"Existing page snapshot has no revision: {page.title}")
        else:
            action = "edited"
        entries.append(
            InterfaceDeployPlanEntry(
                title=page.title,
                source_path=page.source_path.as_posix(),
                source_sha256=source_hash,
                content_model=page.content_model,
                planned_action=action,
                new_text=source_text,
                snapshot=snapshot,
            )
        )

    definition_snapshot = snapshots[DEFINITION_TITLE]
    definition_text = _snapshot_text(definition_snapshot)
    definition_revision = _snapshot_revision(definition_snapshot)
    if definition_text is None or definition_revision is None:
        raise InterfaceDeployError(f"Required page is missing: {DEFINITION_TITLE}")
    new_definition = reconcile_definition(definition_text, spec)
    definition_action: DeployAction = (
        "unchanged" if normalize_saved_text(definition_text) == normalize_saved_text(new_definition) else "edited"
    )
    definition_entry = InterfaceDeployPlanEntry(
        title=DEFINITION_TITLE,
        source_path=definition_path.relative_to(root).as_posix(),
        source_sha256=definition_hash,
        content_model="wikitext",
        planned_action=definition_action,
        new_text=new_definition,
        snapshot=definition_snapshot,
    )
    created = [entry for entry in entries if entry.planned_action == "created"]
    others = [entry for entry in entries if entry.planned_action != "created"]
    return InterfaceDeployPlan(entries=(*created, definition_entry, *others), assert_user=assert_user)


def deploy_interface_pages(
    plan: InterfaceDeployPlan,
    *,
    repo_root: Path,
    client: InterfaceDeployClient,
    summary: str,
    rollback_root: Path,
    checkpoint: Checkpoint,
) -> InterfaceDeployResult:
    """Prepare all sidecars/checkpoints, then mutate sources and definition."""
    if not isinstance(plan, InterfaceDeployPlan):
        raise TypeError("plan must be an InterfaceDeployPlan")
    if not callable(checkpoint):
        raise TypeError("checkpoint must be callable")
    root = repo_root.resolve()
    source_texts, current_snapshots = _validated_plan_texts(root, plan, client)
    rollback_dir = _constrained_rollback_root(root, rollback_root)
    rollback_root_relative = rollback_dir.relative_to(root).as_posix()
    _require_editinterface(client, plan.assert_user)
    edit_account = client.edit_account
    if not edit_account:
        raise InterfaceDeployError("The native client has no edit account")

    prepared: list[InterfacePageManifestEntry] = []
    if any(entry.planned_action == "edited" for entry in plan.entries):
        _ensure_directory(rollback_dir)
    for entry in plan.entries:
        snapshot = current_snapshots[entry.title]
        revision = _snapshot_revision(snapshot)
        old_revision_id = revision.revision_id if entry.planned_action == "edited" and revision else None
        old_timestamp = revision.timestamp if entry.planned_action == "edited" and revision else None
        rollback_source = None
        rollback_digest = None
        if entry.planned_action == "edited":
            remote_text = _snapshot_text(snapshot)
            if remote_text is None or revision is None:
                raise InterfaceDeployError(f"Cannot prepare edited page without revision: {entry.title}")
            sidecar_path = rollback_dir / rollback_sidecar_filename(entry.title)
            sidecar_data = remote_text.encode("utf-8")
            _atomic_write(sidecar_path, sidecar_data)
            rollback_source = sidecar_path.relative_to(root).as_posix()
            rollback_digest = hashlib.sha256(sidecar_data).hexdigest()
        prepared.append(
            InterfacePageManifestEntry(
                title=entry.title,
                source_path=entry.source_path,
                source_sha256=entry.source_sha256,
                content_model=entry.content_model,
                old_revision_id=old_revision_id,
                old_revision_timestamp=old_timestamp,
                rollback_text_source=rollback_source,
                rollback_text_sha256=rollback_digest,
                deployed_text_sha256=_text_digest(source_texts[entry.title]),
                deploy_action=None,
                mutation_state="pending",
                deploy_request_base=snapshot,
                deploy_account=edit_account,
                deploy_api_url=client.api_url,
                deploy_request_state="unattempted",
            )
        )
    prepared_manifest = InterfaceDeployManifest(entries=tuple(prepared), rollback_root=rollback_root_relative)
    _checkpoint(checkpoint, prepared_manifest)

    completed = list(prepared)
    for index, entry in enumerate(plan.entries):
        current = completed[index]
        if entry.planned_action == "unchanged":
            completed[index] = replace(current, deploy_action="unchanged", mutation_state="applied")
            _checkpoint(
                checkpoint, InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative)
            )
            continue
        current = replace(current, deploy_request_state="pending")
        completed[index] = current
        _checkpoint(checkpoint, InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative))
        snapshot = current_snapshots[entry.title]
        try:
            if entry.planned_action == "created":
                revision_id = client.safe_create_page(
                    title=entry.title,
                    content=source_texts[entry.title],
                    start_timestamp=_snapshot_start_timestamp(snapshot),
                    summary=summary,
                    bot=False,
                    assertion="user",
                    assert_user=plan.assert_user,
                    content_model=entry.content_model,
                )
            else:
                revision = _snapshot_revision(snapshot)
                if revision is None:
                    raise InterfaceDeployError(f"Cannot edit page without base revision: {entry.title}")
                revision_id = client.safe_edit_page(
                    title=entry.title,
                    content=source_texts[entry.title],
                    base_revision=revision,
                    summary=summary,
                    bot=False,
                    assertion="user",
                    assert_user=plan.assert_user,
                    content_model=entry.content_model,
                )
            if isinstance(revision_id, bool) or not isinstance(revision_id, int):
                raise InterfaceDeployError(f"MediaWiki did not return a revision id for {entry.title}")
            completed[index] = replace(
                current,
                new_revision_id=revision_id,
                deploy_action=entry.planned_action,
                mutation_state="applied",
            )
        except MediaWikiEditVerificationError as error:
            # The native acknowledgement is stronger than any later current-page read.
            completed[index] = replace(
                current,
                new_revision_id=error.new_revision_id,
                deploy_action=entry.planned_action,
                mutation_state="ambiguous",
                edit_verification_error=_verification_receipt(error),
            )
            recovery_manifest = InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative)
            try:
                _checkpoint(checkpoint, recovery_manifest)
            except BaseException as checkpoint_error:
                raise InterfaceMutationError(
                    f"Verification failed for acknowledged edit of {entry.title} and checkpoint failed",
                    recovery_manifest,
                ) from checkpoint_error
            raise InterfaceMutationError(
                f"Verification failed for acknowledged edit of {entry.title}; rollback evidence checkpointed",
                recovery_manifest,
            ) from error
        except (MediaWikiEditConflictError, MediaWikiAssertionError, MediaWikiPermissionError) as error:
            # Native rejections provide no write receipt and must not adopt another editor's revision.
            completed[index] = replace(current, deploy_request_state="rejected")
            recovery_manifest = InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative)
            try:
                _checkpoint(checkpoint, recovery_manifest)
            except BaseException as checkpoint_error:
                raise InterfaceMutationError(
                    f"Rejected mutation for {entry.title} could not be checkpointed", recovery_manifest
                ) from checkpoint_error
            raise InterfaceDeployError(f"Native mutation rejected for {entry.title}") from error
        except BaseException as error:
            reconciled = _reconcile_mutation(client, entry, source_texts[entry.title], current, plan.assert_user)
            completed[index] = reconciled
            recovery_manifest = InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative)
            try:
                _checkpoint(checkpoint, recovery_manifest)
            except BaseException as checkpoint_error:
                raise InterfaceMutationError(
                    f"Mutation outcome for {entry.title} is ambiguous and checkpoint failed", recovery_manifest
                ) from checkpoint_error
            if reconciled.mutation_state == "applied":
                raise InterfaceDeployError(
                    f"Mutation for {entry.title} committed but response failed; checkpoint reconciled"
                ) from error
            raise InterfaceMutationError(
                f"Mutation outcome for {entry.title} is ambiguous; rollback state checkpointed", recovery_manifest
            ) from error
        try:
            _checkpoint(
                checkpoint,
                InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative),
            )
        except BaseException as error:
            reconciled = _reconcile_mutation(
                client, entry, source_texts[entry.title], completed[index], plan.assert_user
            )
            completed[index] = reconciled
            recovery_manifest = InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative)
            try:
                _checkpoint(checkpoint, recovery_manifest)
            except BaseException as checkpoint_error:
                raise InterfaceMutationError(
                    f"Mutation for {entry.title} committed but checkpoint failed", recovery_manifest
                ) from checkpoint_error
            if reconciled.mutation_state == "applied":
                raise InterfaceDeployError(
                    f"Mutation for {entry.title} committed; checkpoint failure reconciled"
                ) from error
            raise InterfaceMutationError(
                f"Mutation outcome for {entry.title} is ambiguous; rollback state checkpointed", recovery_manifest
            ) from error

    return InterfaceDeployResult(
        manifest=InterfaceDeployManifest(entries=tuple(completed), rollback_root=rollback_root_relative)
    )


def rollback_interface_pages(
    manifest: InterfaceDeployManifest,
    repo_root: Path,
    client: InterfaceDeployClient,
    summary: str,
    force: bool = False,
    assert_user: str | None = None,
    *,
    checkpoint: Checkpoint,
) -> InterfaceRollbackResult:
    """Restore attributable writes using the latest checkpoint of the original manifest.

    Persist each actual rollback request base before writing so retries cannot
    mistake another editor's matching text for this account's restoration.
    """
    if not isinstance(manifest, InterfaceDeployManifest):
        raise TypeError("manifest must be an InterfaceDeployManifest")
    if not callable(checkpoint):
        raise TypeError("checkpoint must be callable")
    root = repo_root.resolve()
    for entry in manifest.entries:
        if entry.rollback_verification_error is not None:
            raise InterfaceMutationError(f"Rollback verification remains unresolved for {entry.title}", manifest)
    manifest = _recover_pending_deploys(manifest, client, assert_user, checkpoint)
    manifest = _recover_pending_rollbacks(manifest, root, client, assert_user, checkpoint)
    created_titles = tuple(
        entry.title
        for entry in manifest.entries
        if entry.deploy_action == "created" and entry.mutation_state != "pending"
    )
    editable = [
        entry for entry in manifest.entries if entry.deploy_action == "edited" and entry.mutation_state != "pending"
    ]
    if editable:
        _require_editinterface(client, assert_user)

    restored: list[InterfaceRollbackEntry] = []
    for original_entry in reversed(editable):
        entry = original_entry
        rollback_text, rollback_model, restored_revision_id = _rollback_target(root, manifest, entry)
        if entry.deploy_api_url is None or entry.deploy_api_url != client.api_url:
            raise InterfaceRevisionConflictError(f"Deployment wiki identity remains unresolved for {entry.title}")

        snapshots = client.get_page_snapshots([entry.title], assertion="user", assert_user=assert_user)
        snapshot = snapshots.get(entry.title)
        if snapshot is None:
            raise InterfaceRevisionConflictError(f"Cannot roll back missing page: {entry.title}")
        current_revision = _snapshot_revision(snapshot)
        current_text = _snapshot_text(snapshot)
        if current_revision is None or current_text is None:
            raise InterfaceRevisionConflictError(f"Cannot roll back page without a current revision: {entry.title}")
        if entry.rollback_request_state != "rejected" and _matches_request(
            snapshot,
            entry.rollback_request_base,
            entry.rollback_account,
            rollback_model,
            _text_digest(rollback_text),
            entry.rollback_new_revision_id,
            request_api_url=entry.rollback_api_url,
            api_url=client.api_url,
        ):
            restored.append(
                InterfaceRollbackEntry(
                    title=entry.title,
                    restored_revision_id=restored_revision_id,
                    new_revision_id=current_revision.revision_id,
                )
            )
            continue
        if normalize_saved_text(current_text) == normalize_saved_text(rollback_text):
            raise InterfaceRevisionConflictError(f"Restored text has no attributable rollback receipt: {entry.title}")
        if entry.new_revision_id is None and not _matches_request(
            snapshot,
            entry.deploy_request_base,
            entry.deploy_account,
            entry.content_model,
            entry.deployed_text_sha256,
            request_api_url=entry.deploy_api_url,
            api_url=client.api_url,
        ):
            raise InterfaceRevisionConflictError(f"Ambiguous deploy has no attributable revision: {entry.title}")
        if not force and entry.new_revision_id is not None and current_revision.revision_id != entry.new_revision_id:
            raise InterfaceRevisionConflictError(
                "Page changed since deploy: "
                f"{entry.title} is at revision {current_revision.revision_id}, "
                f"expected {entry.new_revision_id}"
            )
        entry = replace(
            entry,
            rollback_request_base=snapshot,
            rollback_account=client.edit_account,
            rollback_api_url=client.api_url,
            rollback_request_state="pending",
            rollback_new_revision_id=None,
        )
        manifest = _replace_manifest_entry(manifest, entry)
        _checkpoint(checkpoint, manifest)
        try:
            new_revision_id = client.safe_edit_page(
                title=entry.title,
                content=rollback_text,
                base_revision=current_revision,
                summary=summary,
                bot=False,
                assertion="user",
                assert_user=assert_user,
                content_model=rollback_model,
            )
            if isinstance(new_revision_id, bool) or not isinstance(new_revision_id, int):
                raise InterfaceDeployError(f"MediaWiki did not return a rollback revision id for {entry.title}")
        except MediaWikiEditVerificationError as error:
            failed_entry = replace(
                entry,
                rollback_new_revision_id=error.new_revision_id,
                rollback_verification_error=_verification_receipt(error),
            )
            failed_manifest = _replace_manifest_entry(manifest, failed_entry)
            # Checkpoint the receipt before any further evidence read.
            try:
                _checkpoint(checkpoint, failed_manifest)
            except BaseException as checkpoint_error:
                raise InterfaceMutationError(
                    f"Rollback verification failed for acknowledged edit of {entry.title} and checkpoint failed",
                    failed_manifest,
                ) from checkpoint_error
            raise InterfaceMutationError(
                f"Rollback verification failed for acknowledged edit of {entry.title}; receipt checkpointed",
                failed_manifest,
            ) from error
        except (MediaWikiEditConflictError, MediaWikiAssertionError, MediaWikiPermissionError) as error:
            rejected_entry = replace(entry, rollback_request_state="rejected")
            rejected_manifest = _replace_manifest_entry(manifest, rejected_entry)
            try:
                _checkpoint(checkpoint, rejected_manifest)
            except BaseException as checkpoint_error:
                raise InterfaceMutationError(
                    f"Rejected rollback for {entry.title} could not be checkpointed", rejected_manifest
                ) from checkpoint_error
            raise InterfaceRevisionConflictError(f"Native rollback rejected for {entry.title}") from error
        except BaseException as error:
            try:
                reconciled = client.get_page_snapshots([entry.title], assertion="user", assert_user=assert_user).get(
                    entry.title
                )
            except BaseException as read_error:
                raise InterfaceMutationError(
                    f"Rollback outcome is ambiguous for {entry.title}", manifest
                ) from read_error
            if not _matches_request(
                reconciled,
                entry.rollback_request_base,
                entry.rollback_account,
                rollback_model,
                _text_digest(rollback_text),
                entry.rollback_new_revision_id,
                request_api_url=entry.rollback_api_url,
                api_url=client.api_url,
            ):
                raise InterfaceMutationError(f"Rollback outcome is ambiguous for {entry.title}", manifest) from error
            assert reconciled is not None and reconciled.revision is not None
            new_revision_id = reconciled.revision.revision_id
        entry = replace(entry, rollback_new_revision_id=new_revision_id)
        manifest = _replace_manifest_entry(manifest, entry)
        try:
            _checkpoint(checkpoint, manifest)
        except BaseException as error:
            raise InterfaceMutationError(
                f"Rollback for {entry.title} committed but checkpoint failed", manifest
            ) from error
        restored.append(
            InterfaceRollbackEntry(
                title=entry.title,
                restored_revision_id=restored_revision_id,
                new_revision_id=new_revision_id,
            )
        )
    return InterfaceRollbackResult(entries=tuple(restored), created_titles=created_titles)


def _validated_plan_texts(
    root: Path,
    plan: InterfaceDeployPlan,
    client: InterfaceDeployClient,
) -> tuple[dict[str, str], dict[str, MediaWikiPageSnapshot]]:
    """Re-derive sources and revalidate every planned snapshot immediately before mutation."""
    spec = load_gadget_spec(root)
    source_pages = gadget_source_pages(spec, root)
    expected_layout = [(page.title, page.source_path.as_posix(), page.content_model) for page in source_pages] + [
        (DEFINITION_TITLE, "wiki/gadgets/gadgets.toml", "wikitext")
    ]
    actual_layout = [(entry.title, entry.source_path, entry.content_model) for entry in plan.entries]
    if sorted(actual_layout) != sorted(expected_layout):
        raise InterfaceSourceDriftError("Interface deployment plan no longer matches the repository gadget allowlist")

    titles = [entry.title for entry in plan.entries]
    current_snapshots = client.get_page_snapshots(titles, assertion="user", assert_user=plan.assert_user)
    if set(current_snapshots) != set(titles):
        missing = sorted(set(titles) - set(current_snapshots))
        raise InterfaceRevisionConflictError(f"Missing current page snapshots: {', '.join(missing)}")

    source_texts: dict[str, str] = {}
    for entry in plan.entries:
        if not isinstance(entry.snapshot, MediaWikiPageSnapshot):
            raise InterfaceDeployError(f"Invalid page snapshot for {entry.title}")
        current = current_snapshots[entry.title]
        _verify_snapshot_identity(entry.title, entry.snapshot, current)
        _verify_content_model(entry.title, current, entry.content_model)
        source_path = _safe_repo_path(root, entry.source_path)
        source_bytes = source_path.read_bytes()
        actual_hash = hashlib.sha256(source_bytes).hexdigest()
        if actual_hash != entry.source_sha256:
            raise InterfaceSourceDriftError(
                f"Source hash mismatch for {entry.title}: expected {entry.source_sha256}, got {actual_hash}"
            )

        remote_text = _snapshot_text(current)
        revision = _snapshot_revision(current)
        if entry.title == DEFINITION_TITLE:
            if remote_text is None or revision is None:
                raise InterfaceDeployError(f"Required page is missing: {DEFINITION_TITLE}")
            target_text = reconcile_definition(remote_text, spec)
        else:
            target_text = _decode_source(entry.title, source_bytes)

        if entry.new_text != target_text:
            raise InterfaceSourceDriftError(f"Planned upload text changed for {entry.title}; create a new plan")
        if remote_text is None:
            expected_action: DeployAction = "created"
        elif normalize_saved_text(remote_text) == normalize_saved_text(target_text):
            expected_action = "unchanged"
        elif revision is None:
            raise InterfaceDeployError(f"Existing page snapshot has no revision: {entry.title}")
        else:
            expected_action = "edited"
        if entry.planned_action != expected_action:
            raise InterfaceRevisionConflictError(
                f"Planned action changed for {entry.title}: expected {expected_action}, got {entry.planned_action}"
            )
        source_texts[entry.title] = target_text
    return source_texts, dict(current_snapshots)


def _verify_snapshot_identity(
    title: str,
    planned: MediaWikiPageSnapshot,
    current: MediaWikiPageSnapshot,
) -> None:
    planned_revision = _snapshot_revision(planned)
    current_revision = _snapshot_revision(current)
    if (planned_revision is None) != (current_revision is None):
        raise InterfaceRevisionConflictError(f"Page existence changed after planning: {title}")
    if (
        planned_revision is not None
        and current_revision is not None
        and planned_revision.revision_id != current_revision.revision_id
    ):
        raise InterfaceRevisionConflictError(
            f"Page changed after planning: {title} is at revision {current_revision.revision_id}, "
            f"expected {planned_revision.revision_id}"
        )
    if _snapshot_text(planned) != _snapshot_text(current):
        raise InterfaceRevisionConflictError(f"Page content changed after planning: {title}")


def _verify_content_model(title: str, snapshot: MediaWikiPageSnapshot, expected: ContentModel) -> None:
    actual = snapshot.content_model
    if actual is not None and actual != expected:
        raise InterfaceDeployError(f"Content model mismatch for {title}: remote={actual!r}, expected={expected!r}")


def _require_editinterface(client: InterfaceDeployClient, assert_user: str | None) -> None:
    rights = client.get_current_user_rights(assertion="user", assert_user=assert_user)
    if (
        isinstance(rights, (str, bytes))
        or not isinstance(rights, Collection)
        or not all(isinstance(right, str) for right in rights)
    ):
        raise InterfacePermissionError("MediaWiki returned invalid current-user rights")
    if "editinterface" not in rights:
        raise InterfacePermissionError("The current user lacks the required editinterface right")


def _checkpoint(checkpoint: Checkpoint, manifest: InterfaceDeployManifest) -> None:
    checkpoint(manifest)


def _text_digest(text: str) -> str:
    return hashlib.sha256(normalize_saved_text(text).encode("utf-8")).hexdigest()


def _verification_receipt(error: MediaWikiEditVerificationError) -> InterfaceEditVerificationReceipt:
    return InterfaceEditVerificationReceipt(
        new_revision_id=error.new_revision_id,
        written_snapshot=error.written_snapshot,
        actual_parent_snapshot=error.actual_parent_snapshot,
    )


def _verified_actual_parent(entry: InterfacePageManifestEntry) -> MediaWikiPageSnapshot:
    receipt = entry.edit_verification_error
    assert receipt is not None
    written = receipt.written_snapshot
    parent = receipt.actual_parent_snapshot
    if (
        written is None
        or written.title != entry.title
        or written.revision is None
        or written.revision.title != entry.title
        or written.revision.revision_id != receipt.new_revision_id
        or parent is None
        or parent.title != entry.title
        or parent.revision is None
        or parent.revision.title != entry.title
        or parent.revision.page_id != written.revision.page_id
        or parent.revision.revision_id != written.revision.parent_revision_id
        or parent.source_text is None
        or parent.content_model is None
    ):
        raise InterfaceRevisionConflictError(f"Actual parent evidence remains unresolved for {entry.title}")
    return parent


def _reconcile_mutation(
    client: InterfaceDeployClient,
    plan_entry: InterfaceDeployPlanEntry,
    target_text: str,
    manifest_entry: InterfacePageManifestEntry,
    assert_user: str | None,
) -> InterfacePageManifestEntry:
    """Classify a failed write by reading the authoritative remote page once more."""
    try:
        snapshot = client.get_page_snapshots([plan_entry.title], assertion="user", assert_user=assert_user).get(
            plan_entry.title
        )
    except BaseException:
        return replace(
            manifest_entry,
            deploy_action=plan_entry.planned_action,
            mutation_state="ambiguous",
            new_revision_id=manifest_entry.new_revision_id,
        )
    if snapshot is None:
        return replace(
            manifest_entry,
            deploy_action=plan_entry.planned_action,
            mutation_state="ambiguous",
            new_revision_id=manifest_entry.new_revision_id,
        )
    if _matches_request(
        snapshot,
        manifest_entry.deploy_request_base,
        manifest_entry.deploy_account,
        plan_entry.content_model,
        _text_digest(target_text),
        manifest_entry.new_revision_id,
        request_api_url=manifest_entry.deploy_api_url,
        api_url=client.api_url,
    ):
        assert snapshot.revision is not None
        return replace(
            manifest_entry,
            deploy_action=plan_entry.planned_action,
            mutation_state="applied",
            new_revision_id=snapshot.revision.revision_id,
        )
    return replace(
        manifest_entry,
        deploy_action=plan_entry.planned_action,
        mutation_state="ambiguous",
        new_revision_id=manifest_entry.new_revision_id,
    )


def _replace_manifest_entry(
    manifest: InterfaceDeployManifest, entry: InterfacePageManifestEntry
) -> InterfaceDeployManifest:
    return replace(manifest, entries=tuple(entry if item.title == entry.title else item for item in manifest.entries))


def _rollback_target(
    root: Path, manifest: InterfaceDeployManifest, entry: InterfacePageManifestEntry
) -> tuple[str, str, int | None]:
    """Load the verified rollback source without changing the reviewed sidecar."""
    sidecar_path = _sidecar_path(root, manifest, entry)
    try:
        if sidecar_path.is_symlink() or not sidecar_path.is_file():
            raise InterfaceDeployError(f"Rollback sidecar must be a regular non-symlink file: {sidecar_path}")
        rollback_data = sidecar_path.read_bytes()
        rollback_text = rollback_data.decode("utf-8")
    except InterfaceDeployError:
        raise
    except (OSError, UnicodeError) as error:
        raise InterfaceDeployError(f"Rollback sidecar is unavailable for {entry.title}: {sidecar_path}") from error
    if entry.rollback_text_sha256 is None or hashlib.sha256(rollback_data).hexdigest() != entry.rollback_text_sha256:
        raise InterfaceDeployError(f"Rollback sidecar digest mismatch for {entry.title}")
    if entry.edit_verification_error is not None:
        parent = _verified_actual_parent(entry)
        assert parent.source_text is not None and parent.content_model is not None and parent.revision is not None
        return parent.source_text, parent.content_model, parent.revision.revision_id
    return rollback_text, entry.content_model, entry.old_revision_id


def _recover_pending_rollbacks(
    manifest: InterfaceDeployManifest,
    root: Path,
    client: InterfaceDeployClient,
    assert_user: str | None,
    checkpoint: Checkpoint,
) -> InterfaceDeployManifest:
    """Attribute all outstanding rollback requests before issuing another write."""
    pending = [
        entry
        for entry in manifest.entries
        if (entry.rollback_request_base is not None or entry.rollback_request_state == "pending")
        and entry.rollback_new_revision_id is None
        and entry.rollback_request_state != "rejected"
    ]
    if not pending:
        return manifest
    targets: dict[str, tuple[str, str, int | None]] = {}
    for entry in pending:
        if (
            entry.deploy_api_url is None
            or entry.deploy_api_url != client.api_url
            or entry.rollback_api_url is None
            or entry.rollback_api_url != client.api_url
        ):
            raise InterfaceRevisionConflictError(f"Rollback wiki identity remains unresolved for {entry.title}")
        targets[entry.title] = _rollback_target(root, manifest, entry)
    try:
        snapshots = client.get_page_snapshots(
            [entry.title for entry in pending], assertion="user", assert_user=assert_user
        )
    except BaseException as error:
        raise InterfaceMutationError("Pending interface rollback evidence is unavailable", manifest) from error
    recovered = manifest
    for entry in pending:
        snapshot = snapshots.get(entry.title)
        text, model, _restored_revision_id = targets[entry.title]
        if not _matches_request(
            snapshot,
            entry.rollback_request_base,
            entry.rollback_account,
            model,
            _text_digest(text),
            entry.rollback_new_revision_id,
            request_api_url=entry.rollback_api_url,
            api_url=client.api_url,
        ):
            raise InterfaceRevisionConflictError(
                f"Pending rollback has no attributable rollback receipt: {entry.title}"
            )
        assert snapshot is not None and snapshot.revision is not None
        recovered_entry = replace(entry, rollback_new_revision_id=snapshot.revision.revision_id)
        recovered = _replace_manifest_entry(recovered, recovered_entry)
    try:
        _checkpoint(checkpoint, recovered)
    except BaseException as error:
        raise InterfaceMutationError(
            "Recovered rollback acknowledgements could not be checkpointed", recovered
        ) from error
    return recovered


def _recover_pending_deploys(
    manifest: InterfaceDeployManifest,
    client: InterfaceDeployClient,
    assert_user: str | None,
    checkpoint: Checkpoint,
) -> InterfaceDeployManifest:
    """Resolve every possible crash-window write before restoring any page."""
    pending = [
        entry
        for entry in manifest.entries
        if (
            entry.mutation_state == "pending"
            and entry.deploy_action is None
            and entry.deploy_request_state not in ("unattempted", "rejected")
        )
        or (entry.mutation_state == "ambiguous" and entry.new_revision_id is None)
    ]
    if not pending:
        return manifest
    for entry in pending:
        if entry.deploy_api_url is None or entry.deploy_api_url != client.api_url:
            raise InterfaceRevisionConflictError(f"Deployment wiki identity remains unresolved for {entry.title}")
    try:
        snapshots = client.get_page_snapshots(
            [entry.title for entry in pending], assertion="user", assert_user=assert_user
        )
    except BaseException as error:
        raise InterfaceMutationError("Pending interface deployment evidence is unavailable", manifest) from error
    recovered = manifest
    for entry in pending:
        snapshot = snapshots.get(entry.title)
        if not _matches_request(
            snapshot,
            entry.deploy_request_base,
            entry.deploy_account,
            entry.content_model,
            entry.deployed_text_sha256,
            entry.new_revision_id,
            request_api_url=entry.deploy_api_url,
            api_url=client.api_url,
        ):
            raise InterfaceRevisionConflictError(f"Pending deploy has no attributable revision: {entry.title}")
        assert snapshot is not None and snapshot.revision is not None and entry.deploy_request_base is not None
        action: DeployAction = "created" if entry.deploy_request_base.revision is None else "edited"
        recovered_entry = replace(
            entry,
            deploy_action=action,
            mutation_state="applied",
            new_revision_id=snapshot.revision.revision_id,
        )
        recovered = _replace_manifest_entry(recovered, recovered_entry)
    try:
        _checkpoint(checkpoint, recovered)
    except BaseException as error:
        raise InterfaceMutationError(
            "Recovered interface acknowledgements could not be checkpointed", recovered
        ) from error
    return recovered


def _matches_request(
    snapshot: MediaWikiPageSnapshot | None,
    request_base: MediaWikiPageSnapshot | None,
    account: str | None,
    content_model: str,
    text_digest: str | None,
    acknowledged_revision_id: int | None = None,
    *,
    request_api_url: str | None,
    api_url: str,
) -> bool:
    """Attribute only an exact native request descendant to the configured account."""
    if (
        snapshot is None
        or request_base is None
        or not account
        or text_digest is None
        or not request_api_url
        or request_api_url != api_url
    ):
        return False
    revision = snapshot.revision
    base = request_base.revision
    return (
        revision is not None
        and snapshot.title == request_base.title
        and revision.title == request_base.title
        and revision.page_id > 0
        and (base is None or (base.title == revision.title and revision.page_id == base.page_id))
        and revision.revision_id > 0
        and revision.revision_id != (base.revision_id if base else 0)
        and revision.parent_revision_id == (base.revision_id if base else 0)
        and revision.user == account
        and snapshot.content_model == content_model
        and snapshot.source_text is not None
        and _text_digest(snapshot.source_text) == text_digest
        and (acknowledged_revision_id is None or revision.revision_id == acknowledged_revision_id)
    )


def _atomic_write(path: Path, data: bytes) -> None:
    """Write bytes with exclusive randomized temp creation and durable replacement."""
    if path.exists() and path.is_symlink():
        raise InterfaceDeployError(f"Refusing to overwrite symlink: {path}")
    _ensure_directory(path.parent)
    temporary_path = path.with_name(f".{path.name}.{secrets.token_hex(16)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        try:
            fd = os.open(temporary_path, flags, 0o600)
        except OSError as error:
            raise InterfaceDeployError(f"Cannot create rollback temporary file: {temporary_path}") from error
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("rollback temporary write made no progress")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        temporary_path.replace(path)
        dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        with suppress(FileNotFoundError):
            temporary_path.unlink()


def _ensure_directory(path: Path) -> None:
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        raise InterfaceDeployError(f"Rollback root must be a regular directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise InterfaceDeployError(f"Rollback root must be a regular directory: {path}")


def _constrained_rollback_root(root: Path, rollback_root: Path) -> Path:
    candidate = rollback_root if rollback_root.is_absolute() else root / rollback_root
    if candidate.exists() and candidate.is_symlink():
        raise InterfaceDeployError("rollback_root must not be a symlink")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise InterfaceDeployError("rollback_root must be inside repo_root") from error
    return resolved


def _sidecar_path(root: Path, manifest: InterfaceDeployManifest, entry: InterfacePageManifestEntry) -> Path:
    if manifest.rollback_root is None:
        raise InterfaceDeployError("Manifest has no approved rollback root")
    expected_relative = (Path(manifest.rollback_root) / rollback_sidecar_filename(entry.title)).as_posix()
    if entry.rollback_text_source != expected_relative:
        raise InterfaceDeployError(f"Rollback sidecar filename is not bound to approved root: {entry.title}")
    rollback_candidate = root / Path(manifest.rollback_root)
    if rollback_candidate.exists() and rollback_candidate.is_symlink():
        raise InterfaceDeployError("Approved rollback root must not be a symlink")
    rollback_dir = _safe_repo_path(root, manifest.rollback_root)
    if rollback_dir.is_symlink() or not rollback_dir.is_dir():
        raise InterfaceDeployError(f"Approved rollback root is not a regular directory: {rollback_dir}")
    return rollback_dir / rollback_sidecar_filename(entry.title)


def _safe_repo_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InterfaceDeployError(f"Manifest source path escapes repo_root: {relative}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise InterfaceDeployError(f"Manifest source path escapes repo_root: {relative}") from error
    return resolved


def _snapshot_text(snapshot: MediaWikiPageSnapshot) -> str | None:
    value = snapshot.source_text
    if value is not None and not isinstance(value, str):
        raise InterfaceDeployError("page snapshot source_text is not text")
    return value


def _snapshot_revision(snapshot: MediaWikiPageSnapshot) -> MediaWikiPageRevision | None:
    return snapshot.revision


def _snapshot_start_timestamp(snapshot: MediaWikiPageSnapshot) -> str:
    value = snapshot.start_timestamp
    if not isinstance(value, str) or not value:
        raise InterfaceDeployError("page snapshot has no start timestamp")
    return value


def _decode_source(title: str, source_bytes: bytes) -> str:
    try:
        return source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InterfaceDeployError(f"Source is not UTF-8 text: {title}") from error


__all__ = [
    "DEFINITION_TITLE",
    "InterfaceDeployClient",
    "InterfaceDeployError",
    "InterfaceDeployPlan",
    "InterfaceDeployPlanEntry",
    "InterfaceDeployResult",
    "InterfaceMutationError",
    "InterfacePermissionError",
    "InterfaceRevisionConflictError",
    "InterfaceRollbackEntry",
    "InterfaceRollbackResult",
    "InterfaceSourceDriftError",
    "deploy_interface_pages",
    "plan_interface_pages",
    "rollback_interface_pages",
]
