"""Safe deployment of repo-owned wiki pages."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import quote

from erenshor.application.wiki_deploy.dependencies import (
    literal_dependencies,
    needed_live_modules,
    order_and_check_dependencies,
)
from erenshor.application.wiki_deploy.manifest import (
    DeployAction,
    RepoWikiPageManifest,
    RepoWikiPageManifestEntry,
    validate_repo_page_manifest_for_deploy,
)
from erenshor.application.wiki_deploy.render_check import RenderCheck, check_render
from erenshor.infrastructure.wiki.content import normalize_saved_text

if TYPE_CHECKING:
    from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
    from erenshor.infrastructure.wiki import MediaWikiPageRevision, MediaWikiPageSnapshot
    from erenshor.infrastructure.wiki.client import MediaWikiParse

EditAssertion = Literal["user", "bot"]


class WikiPageDeployClient(Protocol):
    """MediaWiki operations required by repo page deployment."""

    @property
    def edit_account(self) -> str: ...

    def get_page_snapshots(
        self,
        titles: list[str],
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> dict[str, MediaWikiPageSnapshot]: ...

    def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]: ...

    def get_embeddedin_pages(self, title: str, namespaces: Sequence[int] = (0,)) -> tuple[str, ...]: ...

    def parse_wikitext(
        self,
        title: str,
        text: str,
        *,
        sandbox_title: str | None = None,
        sandbox_text: str | None = None,
        sandbox_content_model: str | None = None,
    ) -> MediaWikiParse: ...

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: EditAssertion = "bot",
        assert_user: str | None = None,
    ) -> int: ...

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: EditAssertion = "bot",
        assert_user: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class RepoPageDrift:
    """A target page whose latest revision is by another account and whose text differs from its source."""

    title: str
    revision_id: int
    user: str | None


class RepoPageDriftError(ValueError):
    """Raised before the first write when another account changed target pages."""

    def __init__(self, drift: Sequence[RepoPageDrift]) -> None:
        self.drift = tuple(drift)
        pages = ", ".join(
            f"{item.title} (revision {item.revision_id} by {item.user or 'a hidden user'})" for item in self.drift
        )
        super().__init__(f"Another account made the latest revision of pages that differ from the repository: {pages}")


def repo_page_action(snapshot: MediaWikiPageSnapshot, source_text: str) -> DeployAction:
    """Return what a deploy does with one page: create it, edit it, or leave it unchanged."""
    if snapshot.source_text is None:
        return "created"
    if normalize_saved_text(snapshot.source_text) == normalize_saved_text(source_text):
        return "unchanged"
    return "edited"


def read_repo_page_sources(manifest: RepoWikiPageManifest, repo_root: Path) -> dict[str, str]:
    """Return the source text of each manifest page, after checking its recorded hash."""
    source_texts: dict[str, str] = {}
    for entry in manifest.entries:
        source_bytes = (repo_root / entry.source_path).read_bytes()
        actual_hash = hashlib.sha256(source_bytes).hexdigest()
        if actual_hash != entry.source_sha256:
            raise ValueError(
                f"Source hash mismatch for {entry.title}: expected {entry.source_sha256}, got {actual_hash}"
            )
        source_texts[entry.title] = source_bytes.decode("utf-8")
    return source_texts


def find_drift(
    entries: Sequence[RepoWikiPageManifestEntry],
    source_texts: Mapping[str, str],
    snapshots: Mapping[str, MediaWikiPageSnapshot],
    *,
    deploy_account: str,
    accepted: Collection[str] = (),
) -> tuple[RepoPageDrift, ...]:
    """Return the pages that a deploy would overwrite after another account's edit.

    A page drifted when its latest revision is by an account other than
    ``deploy_account`` and its text differs from the source. A page that
    ``accepted`` names was reviewed, so it is not drift.

    Raises:
        ValueError: The deploying account is unknown, or ``accepted`` names a
            page outside ``entries``.
    """
    if not deploy_account:
        raise ValueError("The deploying account is unknown. Set bot_username in the local configuration.")
    outside = sorted(set(accepted) - {entry.title for entry in entries})
    if outside:
        raise ValueError(f"Accepted drift names pages outside this deploy: {', '.join(outside)}")
    drift: list[RepoPageDrift] = []
    for entry in entries:
        snapshot = snapshots[entry.title]
        revision = snapshot.revision
        if revision is None or repo_page_action(snapshot, source_texts[entry.title]) != "edited":
            continue
        if revision.user != deploy_account and entry.title not in accepted:
            drift.append(RepoPageDrift(entry.title, revision.revision_id, revision.user))
    return tuple(drift)


def prepare_repo_page_checks(
    manifest: RepoWikiPageManifest,
    source_texts: Mapping[str, str],
    snapshots: Mapping[str, MediaWikiPageSnapshot],
    client: WikiPageDeployClient,
    live_modules: dict[str, str | None] | None = None,
) -> RepoWikiPageManifest:
    """Check transitive module dependencies and order the planned writes."""
    changed = RepoWikiPageManifest(
        entries=tuple(
            entry
            for entry in manifest.entries
            if repo_page_action(snapshots[entry.title], source_texts[entry.title]) != "unchanged"
        )
    )
    live = needed_live_modules({entry.title: source_texts[entry.title] for entry in changed.entries}, client)
    live.update({title: snapshot.source_text for title, snapshot in snapshots.items() if title not in live})
    if live_modules is not None:
        live_modules.update(live)
    ordered = order_and_check_dependencies(changed, source_texts, live)
    positions = {entry.title: index for index, entry in enumerate(ordered.entries)}
    stages = {
        name: index
        for index, name in enumerate(
            ("generated_data", "lua_module", "cargo_declaration", "template", "content_page", "article")
        )
    }
    return RepoWikiPageManifest(
        entries=tuple(
            sorted(
                manifest.entries,
                key=lambda entry: (stages[entry.upload_stage], positions.get(entry.title, len(positions)), entry.title),
            )
        )
    )


def render_repo_page_checks(
    manifest: RepoWikiPageManifest,
    source_texts: Mapping[str, str],
    snapshots: Mapping[str, MediaWikiPageSnapshot],
    client: WikiPageDeployClient,
    *,
    catalog: Mapping[str, LinkCatalogEntry],
    full: bool = False,
    dry_run: bool = False,
    live_modules: Mapping[str, str | None] | None = None,
    report: Callable[[RenderCheck], None] | None = None,
) -> None:
    """Check each changed module and template before its write or dry-run preview."""
    live_cache: dict[str, MediaWikiParse] = {}
    changed = {
        entry.title
        for entry in manifest.entries
        if repo_page_action(snapshots[entry.title], source_texts[entry.title]) != "unchanged"
    }

    def depends_on_changed_module(root: str) -> bool:
        visited: set[str] = {root}
        pending = list(literal_dependencies(root, source_texts[root]))
        while pending:
            title = pending.pop()
            if title in changed and title != root:
                return True
            if title in visited:
                continue
            visited.add(title)
            text = (live_modules or {}).get(title)
            if text is None and title in source_texts:
                text = snapshots[title].source_text
            if text is not None:
                pending.extend(literal_dependencies(title, text))
        return False

    for entry in manifest.entries:
        if entry.title not in changed or entry.upload_stage not in {
            "generated_data",
            "lua_module",
            "cargo_declaration",
            "template",
        }:
            continue
        provisional = dry_run and depends_on_changed_module(entry.title)
        result = check_render(
            client,
            entry.title,
            source_texts[entry.title],
            catalog=catalog,
            live_cache=live_cache,
            full=full,
            provisional=provisional,
        )
        if report is not None:
            report(result)


@dataclass(frozen=True, slots=True)
class RepoPageDeployResultEntry:
    """Deployment result for one manifest page."""

    title: str
    status: DeployAction
    old_revision_id: int | None
    old_revision_timestamp: str | None
    new_revision_id: int | None
    rollback_text_source: str | None = None


@dataclass(frozen=True, slots=True)
class RepoPageDeployResult:
    """Deployment result for a repo-owned page manifest."""

    entries: tuple[RepoPageDeployResultEntry, ...]


def deploy_repo_pages(
    *,
    manifest: RepoWikiPageManifest,
    repo_root: Path,
    client: WikiPageDeployClient,
    summary: str,
    assertion: EditAssertion,
    assert_user: str | None = None,
    rollback_root: Path | None = None,
    checkpoint: Callable[[RepoWikiPageManifest], None] | None = None,
    include_templates: bool = False,
    include_generated_data: bool = False,
    include_content_pages: bool = False,
    accept_drift: Collection[str] = (),
    catalog: Mapping[str, LinkCatalogEntry] | None = None,
    full_render_check: bool = False,
    report_render: Callable[[RenderCheck], None] | None = None,
) -> RepoPageDeployResult:
    """Deploy changed manifest pages through the safe MediaWiki edit path.

    All source hashes, remote snapshots, and rollback sidecars are prepared before
    the first mutation. Every safe edit uses the revision returned alongside the
    source text it was compared with. A page that another account changed and
    that ``accept_drift`` does not name stops the deploy before the first
    mutation (see ``find_drift``).

    Raises:
        RepoPageDriftError: Another account made the latest revision of pages
            that differ from their sources.
    """
    validate_repo_page_manifest_for_deploy(
        manifest,
        include_templates=include_templates,
        include_generated_data=include_generated_data,
        include_content_pages=include_content_pages,
    )
    if not manifest.entries:
        return RepoPageDeployResult(entries=())
    titles = [entry.title for entry in manifest.entries]
    source_texts = read_repo_page_sources(manifest, repo_root)

    snapshots = client.get_page_snapshots(titles, assertion=assertion, assert_user=assert_user)
    missing = [title for title in titles if title not in snapshots]
    if missing:
        raise ValueError(f"Missing page snapshot for requested title: {missing[0]}")
    drift = find_drift(
        manifest.entries, source_texts, snapshots, deploy_account=client.edit_account, accepted=accept_drift
    )
    if drift:
        raise RepoPageDriftError(drift)
    manifest = prepare_repo_page_checks(manifest, source_texts, snapshots, client)

    prepared_entries = []
    for entry in manifest.entries:
        snapshot = snapshots[entry.title]
        remote_text = snapshot.source_text
        changed = repo_page_action(snapshot, source_texts[entry.title]) != "unchanged"
        rollback_text_source = None
        old_revision_id = None
        old_revision_timestamp = None
        if changed and remote_text is not None:
            if snapshot.revision is None:
                raise ValueError(f"Remote page snapshot has no revision: {entry.title}")
            old_revision_id = snapshot.revision.revision_id
            old_revision_timestamp = snapshot.revision.timestamp
            if rollback_root is not None:
                rollback_path = rollback_root / rollback_filename(entry.title)
                rollback_path.parent.mkdir(parents=True, exist_ok=True)
                rollback_path.write_text(remote_text, encoding="utf-8")
                rollback_text_source = rollback_path.relative_to(repo_root).as_posix()
        prepared_entries.append(
            replace(
                entry,
                old_revision_id=old_revision_id,
                old_revision_timestamp=old_revision_timestamp,
                new_revision_id=None,
                new_revision_timestamp=None,
                rollback_text_source=rollback_text_source,
                deploy_action=None,
            )
        )

    prepared_manifest = RepoWikiPageManifest(entries=tuple(prepared_entries))
    if checkpoint is not None:
        checkpoint(prepared_manifest)

    live_parse_cache: dict[str, MediaWikiParse] = {}
    result_entries: list[RepoPageDeployResultEntry] = []
    for entry, prepared_entry in zip(manifest.entries, prepared_manifest.entries, strict=True):
        snapshot = snapshots[entry.title]
        source_text = source_texts[entry.title]
        remote_text = snapshot.source_text
        if repo_page_action(snapshot, source_text) == "unchanged":
            result_entries.append(
                RepoPageDeployResultEntry(
                    title=entry.title,
                    status="unchanged",
                    old_revision_id=None,
                    old_revision_timestamp=None,
                    new_revision_id=None,
                    rollback_text_source=None,
                )
            )
            continue
        if entry.upload_stage in {"generated_data", "lua_module", "cargo_declaration", "template"}:
            rendered = check_render(
                client,
                entry.title,
                source_text,
                catalog=catalog or {},
                live_cache=live_parse_cache,
                full=full_render_check,
            )
            if report_render is not None:
                report_render(rendered)

        if remote_text is None:
            new_revision_id = client.safe_create_page(
                title=entry.title,
                content=source_text,
                start_timestamp=snapshot.start_timestamp,
                summary=summary,
                assertion=assertion,
                assert_user=assert_user,
            )
            result_entries.append(
                RepoPageDeployResultEntry(
                    title=entry.title,
                    status="created",
                    old_revision_id=None,
                    old_revision_timestamp=None,
                    new_revision_id=new_revision_id,
                    rollback_text_source=None,
                )
            )
        else:
            base_revision = snapshot.revision
            if base_revision is None:
                raise ValueError(f"Remote page snapshot has no revision: {entry.title}")
            new_revision_id = client.safe_edit_page(
                title=entry.title,
                content=source_text,
                base_revision=base_revision,
                summary=summary,
                assertion=assertion,
                assert_user=assert_user,
            )
            result_entries.append(
                RepoPageDeployResultEntry(
                    title=entry.title,
                    status="edited",
                    old_revision_id=prepared_entry.old_revision_id,
                    old_revision_timestamp=prepared_entry.old_revision_timestamp,
                    new_revision_id=new_revision_id,
                    rollback_text_source=prepared_entry.rollback_text_source,
                )
            )
        # A completed write can change the live render of another selected page.
        live_parse_cache.clear()

        if checkpoint is not None:
            checkpoint(build_deployed_manifest(prepared_manifest, RepoPageDeployResult(entries=tuple(result_entries))))

    return RepoPageDeployResult(entries=tuple(result_entries))


def rollback_filename(title: str) -> str:
    """Return a deterministic, collision-free rollback file name for a MediaWiki title.

    Percent-encoding every reserved character keeps the mapping injective (distinct
    titles never share a sidecar file) and flat (title slashes do not become path
    separators), unlike a lossy "replace reserved runs with underscore" scheme.
    """
    return f"{quote(title, safe='')}.wiki"


def build_deployed_manifest(manifest: RepoWikiPageManifest, result: RepoPageDeployResult) -> RepoWikiPageManifest:
    """Merge deploy outcomes into the source manifest to produce a rollback manifest.
    Source-of-truth fields (title, source path, hash, ownership, Cargo metadata)
    are preserved; the revision IDs and rollback text source observed during the
    deploy are recorded so a later rollback can restore the prior page text.
    """
    result_by_title = {entry.title: entry for entry in result.entries}
    merged_entries = []
    for entry in manifest.entries:
        result_entry = result_by_title.get(entry.title)
        if result_entry is None:
            merged_entries.append(entry)
            continue
        merged_entries.append(
            replace(
                entry,
                old_revision_id=result_entry.old_revision_id,
                old_revision_timestamp=result_entry.old_revision_timestamp,
                new_revision_id=result_entry.new_revision_id,
                rollback_text_source=result_entry.rollback_text_source,
                deploy_action=result_entry.status,
            )
        )
    return RepoWikiPageManifest(entries=tuple(merged_entries))
