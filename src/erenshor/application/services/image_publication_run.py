"""Carrying out a publication plan and reverting a run (design D8 of rebuild-game-image-pipeline).

A run moves files first, then uploads, then writes redirects to the pictures'
files, then deletes each copy followed at once by the redirect that replaces
it, and deletes the orphans last. Every native page edit first checkpoints its
reviewed source, intended source and account in the run ledger. An unknown
outcome stops the run and stays pending. Revert reconciles all pending edits
read-only from account, exact parent, page, source and model evidence before
undoing earlier uploads. Missing evidence blocks recovery without replaying
the request. A failed verification retains the acknowledged revision and its
actual parent separately from the reviewed preimage.
Recovery records its request reference and completed restoration revision in
the original run, so a later file-recovery failure does not replay restored
page edits. Completed restorations are checked historically, not by matching
the current page's text. Every known native edit remains bound to its recorded
wiki endpoint before recovery can change pages or earlier files.
An upload never ignores MediaWiki's warnings up front: when the wiki answers
only with warnings that the verdict expects, the run confirms the stashed
upload, and otherwise it skips the title. The bot account uploads and edits. An administrator's account
with the delete and file-move grants moves and deletes, because administrators
skip the wiki's limit of 8 moves a minute that bot accounts have.

Page edit intent goes to ``run.json`` before the request. Other writes are
recorded when acknowledged, with the bytes an update replaced and the
description of a deleted copy. A revert uploads
the replaced bytes again, restores deleted files, restores a redirect it
changed, and moves a moved file back without a redirect. Created files and
created redirects stay, and the revert lists them.

wiki.gg's CDN sometimes caches a request that lands on a title's raw image
URL in the moment between a write and the backend settling, and goes on
serving those wrong bytes under the correct, versioned URL until something
purges it (observed on 823 of 2,794 titles after the picture cutover of
2026-10-08, confirmed fixed one by one with ``action=purge``). A successful
upload or move purges its title at once so readers never see this.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger

from erenshor.application.wiki_deploy.manifest import durable_write_text
from erenshor.application.wiki_deploy.pages import remote_write_rejected
from erenshor.domain.value_objects.wiki_filename import render_body
from erenshor.infrastructure.wiki import (
    MediaWikiAPIError,
    MediaWikiEditVerificationError,
    MediaWikiNetworkError,
    MediaWikiUploadWarningError,
)
from erenshor.infrastructure.wiki.content import normalize_saved_text

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from erenshor.application.services.image_publication import (
        Catalog,
        Orphan,
        Picture,
        PlannedTitle,
        PublishPlan,
    )
    from erenshor.infrastructure.wiki.client import (
        MediaWikiFileVersion,
        MediaWikiPageRevision,
        MediaWikiPageSnapshot,
    )

__all__ = [
    "AdministratorWriter",
    "PublishWriter",
    "RunRecord",
    "comment",
    "description",
    "execute",
    "move",
    "redirect",
    "revert",
]

_REDIRECT = re.compile(r"^\s*#REDIRECT\s*\[\[\s*:?\s*([^\]|]+?)\s*(?:\|[^\]]*)?\]\]", re.IGNORECASE)


class PublishWriter(Protocol):
    """The reads and writes of the bot account that a run needs."""

    api_url: str

    @property
    def edit_account(self) -> str: ...

    def get_file_versions(self, title: str, limit: int = 50) -> tuple[MediaWikiFileVersion, ...]: ...

    def get_page_snapshots(self, titles: Sequence[str]) -> dict[str, MediaWikiPageSnapshot]: ...

    def get_revision_snapshots(self, revision_ids: Sequence[int]) -> dict[int, MediaWikiPageSnapshot]: ...

    def is_file_used(self, title: str) -> bool: ...

    def download(self, url: str) -> bytes: ...

    def upload_file(
        self, file_path: str, filename: str, comment: str, text: str = "", ignore_warnings: bool = False
    ) -> dict[str, Any]: ...

    def confirm_upload(self, filekey: str, filename: str, comment: str, text: str = "") -> dict[str, Any]: ...

    def safe_create_page(self, title: str, content: str, start_timestamp: str, summary: str | None = None) -> int: ...

    def safe_edit_page(
        self, title: str, content: str, base_revision: MediaWikiPageRevision, summary: str | None = None
    ) -> int: ...

    def purge_pages(self, titles: Sequence[str], force_link_update: bool = True) -> tuple[str, ...]: ...


class AdministratorWriter(Protocol):
    """The moves and deletions of an administrator's account that a run and its revert need."""

    def move_page(self, from_title: str, to_title: str, reason: str, *, leave_redirect: bool = True) -> None: ...

    def delete_page(self, title: str, reason: str) -> None: ...

    def undelete_page(self, title: str, reason: str) -> None: ...

    def purge_pages(self, titles: Sequence[str], force_link_update: bool = True) -> tuple[str, ...]: ...


def comment(picture: Picture, game_build: str) -> str:
    """The upload comment that records a picture's provenance."""
    return f"Game picture {picture.image_hash} ({picture.kind} from {picture.source}, game build {game_build})"


def _purge(client: PublishWriter | AdministratorWriter, titles: Sequence[str]) -> None:
    """Purge a title's CDN cache after a write, best-effort: a failure here does not undo the write."""
    try:
        client.purge_pages(titles, force_link_update=False)
    except MediaWikiAPIError as error:
        logger.warning(f"Purging {', '.join(titles)} after the write failed: {error}")


def description(picture: Picture, game_build: str, entity_key: str, title: str) -> str:
    """The description page of a new file: how the picture was made, and the game's copyright notice.

    ``entity_key`` is the stable key of the first entity whose page names the
    file, which tells a render of an item from a render of a character, and
    ``title`` names the body that an item's render shows, if one.
    """
    if picture.kind == "render":
        body = render_body(title)
        if not entity_key.startswith("item:"):
            shows = "the character"
        elif body is None:
            shows = "the item by itself"
        else:
            shows = f"the item by itself, as the {body} body wears it"
        made = (
            f"Rendered from the game's model of {shows} (game build {picture.approved_build}, capture preset "
            f"{picture.capture_preset}) and approved after review. An in-game screenshot belongs under the "
            "screenshot title that the infobox names, and shows beside this render."
        )
    else:
        made = f"The game's icon, from the texture {picture.source} of game build {game_build}, unchanged."
    return f"== Summary ==\n{made}\n\n== Licensing ==\n{{{{License|Game}}}}\n"


@dataclass
class RunRecord:
    """Save native edit intent before requesting a write and resolve that same entry.

    ``done=None`` with ``pending_mutation`` means the write outcome is unknown.
    ``done`` otherwise records a known mutation, not verification success.
    ``requires_rollback`` keeps the reviewed snapshot separate from the actual
    written revision and its parent, so recovery cannot substitute a reviewed
    preimage for an intervening editor's revision.
    Restoration references are saved here before the recovery request, so a
    stopped recovery can attribute its result from the existing recovery ledger.
    """

    directory: Path
    entries: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, directory: Path) -> RunRecord:
        path = directory / "run.json"
        entries = json.loads(path.read_text(encoding="utf-8"))["entries"] if path.is_file() else []
        return cls(directory, entries)

    def add(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)
        self.save()

    def update(self, entry: dict[str, Any], **values: Any) -> None:
        entry.update(values)
        self.save()

    def save(self) -> None:
        """Durably checkpoint the authoritative ledger without adding a second event for an intent."""
        durable_write_text(
            self.directory / "run.json",
            json.dumps({"entries": self.entries}, indent=2, ensure_ascii=False) + "\n",
        )


def _verification_failed(
    record: RunRecord,
    error: MediaWikiEditVerificationError,
    entry: dict[str, Any],
    reviewed: MediaWikiPageSnapshot,
) -> None:
    """Retain the acknowledged write independently of whether its evidence can be saved."""
    failure = {
        "done": True,
        "pending_mutation": False,
        "mutation_state": "acknowledged",
        "verified": False,
        "requires_rollback": True,
        "revision": error.new_revision_id,
        "reason": str(error),
        "reviewed_snapshot": asdict(reviewed),
        "written_snapshot": asdict(error.written_snapshot) if error.written_snapshot is not None else None,
        "actual_parent_snapshot": (
            asdict(error.actual_parent_snapshot) if error.actual_parent_snapshot is not None else None
        ),
    }
    try:
        record.update(entry, **failure)
    except Exception as persistence_error:
        # RunRecord retains the entry in memory before attempting durable I/O.
        error.add_note(f"Saving image revision {error.new_revision_id} failed: {persistence_error}")


def _write_page(
    entry: dict[str, Any],
    page: MediaWikiPageSnapshot,
    text: str,
    writer: PublishWriter,
    record: RunRecord,
    *,
    summary: str,
    restoration_of: tuple[RunRecord, dict[str, Any]] | None = None,
) -> int | None:
    """Persist intent before native I/O and stop on every outcome that is not a proven rejection."""
    if any(previous.get("pending_mutation") for previous in record.entries):
        raise ValueError("Resolve the image run's pending native edit before another write")
    model = page.content_model if page.revision is not None else "wikitext"
    if not model:
        raise ValueError(f"Cannot record recoverable edit intent without a content model: {page.title}")
    entry.update(
        done=None,
        pending_mutation=True,
        mutation_state="pending",
        reviewed_snapshot=asdict(page),
        intended_source=text,
        intended_source_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        intended_content_model=model,
        edit_account=writer.edit_account,
        api_url=writer.api_url,
        summary=summary,
    )
    record.add(entry)
    if restoration_of is not None:
        authority, original = restoration_of
        authority.update(
            original,
            restoration_record=str(record.directory.resolve()),
            restoration_entry=len(record.entries) - 1,
        )
    try:
        if page.revision is None:
            revision = writer.safe_create_page(page.title, text, page.start_timestamp, summary=summary)
        else:
            revision = writer.safe_edit_page(page.title, text, page.revision, summary=summary)
    except MediaWikiEditVerificationError as error:
        _verification_failed(record, error, entry, page)
        raise
    except BaseException as error:
        rejected = isinstance(error, MediaWikiAPIError) and remote_write_rejected(error)
        try:
            record.update(
                entry,
                done=False if rejected else None,
                pending_mutation=not rejected,
                mutation_state="rejected" if rejected else "ambiguous",
                reason=str(error),
            )
        except Exception as persistence_error:
            error.add_note(f"Saving image edit outcome failed: {persistence_error}")
        if rejected:
            return None
        raise
    record.update(
        entry,
        done=page.revision is None or revision != page.revision.revision_id,
        pending_mutation=False,
        mutation_state="applied",
        verified=True,
        revision=revision,
    )
    if restoration_of is not None:
        authority, original = restoration_of
        authority.update(original, restoration_revision=revision, requires_rollback=False)
    return revision


def execute(
    plan: PublishPlan,
    catalog: Catalog,
    writer: PublishWriter,
    administrator: AdministratorWriter | None,
    record: RunRecord,
    *,
    summary: str,
) -> None:
    """Carry out a plan so that no title that a page shows goes without a picture for long.

    Moves come first, and each is followed at once by the redirects that named
    its old title, so they stop leading through a redirect within seconds.
    Then uploads. Then every other title that should redirect to a picture's
    file does, which also takes the old titles that redirect to a copy off it
    before the copy goes. Then each copy is deleted and its title redirects to
    the picture's file at once. The orphans go last. A title whose picture's
    file could not be moved or uploaded is left as it is.

    Raises:
        ValueError: If the plan moves or deletes and no administrator is given.
    """
    if any(entry.get("pending_mutation") for entry in record.entries):
        raise ValueError("Resolve the image run's pending native edit before another write")
    if plan.needs_administrator and administrator is None:
        raise ValueError("The plan moves or deletes files, which needs the administrator account")
    missing_files: set[str] = set()
    followers: dict[str, list[PlannedTitle]] = {}
    for item in plan.titles:
        if item.verdict == "redirect" and item.redirect_target is not None:
            followers.setdefault(item.redirect_target, []).append(item)
    followed: set[str] = set()
    for item in plan.titles:
        if item.verdict != "move":
            continue
        assert administrator is not None  # needs_administrator holds for a plan with moves
        if not move(
            str(item.source), item.title, str(item.source_sha1), writer, administrator, record=record, summary=summary
        ):
            missing_files.add(item.title)
            continue
        for follower in followers.get(str(item.source), ()):
            redirect(follower.title, str(follower.file), follower.redirect_target, writer, record, summary=summary)
            followed.add(follower.title)
    for item in plan.titles:
        if item.verdict in ("create", "update"):
            uploaded = _upload(item, catalog, writer, record)
            if not uploaded and item.verdict == "create":
                missing_files.add(item.title)
            if uploaded and item.verdict == "update" and item.redirect_target is not None:
                _describe(item, catalog, writer, record, summary)
        elif item.verdict == "describe":
            _describe(item, catalog, writer, record, summary)

    def has_file(item: PlannedTitle) -> bool:
        if item.file is None or item.file in missing_files:
            record.add(_skipped(item, item.verdict, "the picture's file was not uploaded"))
            return False
        return True

    for item in plan.titles:
        if item.verdict == "redirect" and item.title not in followed and has_file(item):
            redirect(item.title, str(item.file), item.redirect_target, writer, record, summary=summary)
    if administrator is None:
        return
    for item in plan.titles:
        if item.verdict == "retire" and has_file(item) and _delete_copy(item, writer, administrator, record, summary):
            redirect(item.title, str(item.file), item.redirect_target, writer, record, summary=summary)
    for orphan in plan.orphans:
        _delete_orphan(orphan, writer, administrator, record, summary)


def _skipped(item: PlannedTitle, action: str, reason: str) -> dict[str, Any]:
    return _not_done(item.title, action, reason)


def _not_done(title: str, action: str, reason: str) -> dict[str, Any]:
    return {"title": title, "action": action, "done": False, "reason": reason}


def _describe(item: PlannedTitle, catalog: Catalog, writer: PublishWriter, record: RunRecord, summary: str) -> None:
    """Replace a redirect on the description page of the picture's file with the picture's description."""
    page = writer.get_page_snapshots([item.title])[item.title]
    current_target = _redirect_target(page.source_text or "")
    if page.revision is None or current_target is None or not _same_title(current_target, item.redirect_target):
        record.add(_skipped(item, "describe", "the page changed since the plan"))
        return
    text = description(
        catalog.pictures[item.image_hash], catalog.game_build, catalog.entities.get(item.title, ""), item.title
    )
    _write_page(
        {"title": item.title, "action": "describe", "text": text, "old_text": page.source_text},
        page,
        text,
        writer,
        record,
        summary=summary,
    )


def _current(writer: PublishWriter, title: str) -> MediaWikiFileVersion | None:
    versions = writer.get_file_versions(title, limit=1)
    return versions[0] if versions else None


def move(
    source: str,
    title: str,
    sha1: str,
    writer: PublishWriter,
    administrator: AdministratorWriter,
    *,
    record: RunRecord,
    summary: str,
) -> bool:
    """Move the file at ``source`` to ``title`` with its history, leaving a redirect at the old title.

    The move goes ahead only while the old title holds the file with ``sha1``
    and the new title has no page. Returns whether the new title holds the file.
    """
    current = _current(writer, source)
    if current is None or current.sha1 != sha1:
        record.add(_not_done(title, "move", f"the file at {source} changed since the plan"))
        return False
    page = writer.get_page_snapshots([title])[title]
    if page.source_text is not None or _current(writer, title) is not None:
        record.add(_not_done(title, "move", "the title gained a page since the plan"))
        return False
    try:
        administrator.move_page(source, title, f"{summary}: the file takes the title that the wiki's pages name")
    except MediaWikiAPIError as error:
        # A move whose answer was lost may have happened: the new title then holds the file.
        landed = _current(writer, title) if isinstance(error, MediaWikiNetworkError) else None
        if landed is None or landed.sha1 != sha1:
            record.add(_not_done(title, "move", f"the move failed: {error}"))
            return False
    moved = _current(writer, title)
    record.add({"title": title, "action": "move", "done": True, "source": source, "sha1": sha1})
    if moved is None or moved.sha1 != sha1:
        record.add(_not_done(title, "move", "the moved file does not have the planned SHA-1"))
        return False
    _purge(administrator, (title, source))
    return True


def _upload(item: PlannedTitle, catalog: Catalog, writer: PublishWriter, record: RunRecord) -> bool:
    picture = catalog.pictures[item.image_hash]
    current = _current(writer, item.title)
    if item.verdict == "create":
        page = writer.get_page_snapshots([item.title])[item.title]
        if current is not None or page.source_text is not None:
            who = f", uploaded by {current.user}" if current is not None else ""
            record.add(_skipped(item, item.verdict, f"the title gained a page since the plan{who}"))
            return False
    elif current is None or current.sha1 != item.live_sha1:
        who = f", now uploaded by {current.user}" if current is not None else ""
        record.add(_skipped(item, item.verdict, f"the file changed since the plan{who}"))
        return False

    replaced = None
    if current is not None:
        replaced = record.directory / "replaced" / f"{current.sha1}.bin"
        if not replaced.is_file():
            replaced.parent.mkdir(parents=True, exist_ok=True)
            replaced.write_bytes(writer.download(current.url))
    name = item.title.removeprefix("File:")
    upload_comment = comment(picture, catalog.game_build)
    text = description(picture, catalog.game_build, catalog.entities.get(item.title, ""), item.title)
    try:
        try:
            writer.upload_file(str(picture.path), name, upload_comment, text=text, ignore_warnings=False)
        except MediaWikiUploadWarningError as warning:
            unexpected = set(warning.warnings) - set(item.warnings)
            if unexpected or warning.filekey is None:
                record.add(_skipped(item, item.verdict, f"MediaWiki warned: {', '.join(sorted(warning.warnings))}"))
                return False
            writer.confirm_upload(warning.filekey, name, upload_comment, text=text)
    except MediaWikiAPIError as error:
        record.add(_skipped(item, item.verdict, f"the upload failed: {error}"))
        return False
    record.add(
        {
            "title": item.title,
            "action": item.verdict,
            "done": True,
            "old_sha1": current.sha1 if current is not None else None,
            "new_sha1": picture.sha1,
            "replaced": str(replaced.relative_to(record.directory)) if replaced is not None else None,
        }
    )
    _purge(writer, (item.title,))
    return True


def _delete_copy(
    item: PlannedTitle, writer: PublishWriter, administrator: AdministratorWriter, record: RunRecord, summary: str
) -> bool:
    current = _current(writer, item.title)
    if current is None or current.sha1 != item.live_sha1:
        record.add(_skipped(item, "retire", "the file changed since the plan"))
        return False
    page = writer.get_page_snapshots([item.title])[item.title]
    try:
        administrator.delete_page(item.title, f"{summary}: a copy of {item.file}, which holds the picture")
    except MediaWikiAPIError as error:
        record.add(_skipped(item, "retire", f"the deletion failed: {error}"))
        return False
    record.add(
        {
            "title": item.title,
            "action": "retire",
            "done": True,
            "sha1": current.sha1,
            "file": item.file,
            "description": page.source_text,
        }
    )
    _purge(administrator, (item.title,))
    return True


def _delete_orphan(
    orphan: Orphan, writer: PublishWriter, administrator: AdministratorWriter, record: RunRecord, summary: str
) -> None:
    entry: dict[str, Any] = {"title": orphan.title, "action": "orphan", "done": False}
    current = _current(writer, orphan.title)
    if current is None or current.sha1 != orphan.sha1:
        record.add(entry | {"reason": "the file changed since the plan"})
        return
    if writer.is_file_used(orphan.title):
        record.add(entry | {"reason": "a page shows the file since the plan"})
        return
    redirects = [
        title
        for title, page in writer.get_page_snapshots(orphan.redirects).items()
        if _same_title(_redirect_target(page.source_text or "") or "", orphan.title)
    ]
    reason = f"{summary}: nothing produces the file and no page shows it"
    try:
        administrator.delete_page(orphan.title, reason)
        for title in redirects:
            administrator.delete_page(title, reason)
    except MediaWikiAPIError as error:
        record.add(entry | {"reason": f"the deletion failed: {error}"})
        return
    record.add(entry | {"done": True, "sha1": current.sha1, "redirects": redirects})
    _purge(administrator, (orphan.title, *redirects))


def redirect(
    title: str,
    target: str,
    expected: str | None,
    writer: PublishWriter,
    record: RunRecord,
    *,
    summary: str,
) -> None:
    """Create the title's redirect to ``target``, or point its redirect there while it still names ``expected``.

    The page decides: the file history of a redirect title is its target's, so
    a file at the title shows as a page that is not a redirect.
    """
    content = f"#REDIRECT [[{target}]]"
    page = writer.get_page_snapshots([title])[title]
    if page.source_text is not None:
        current_target = _redirect_target(page.source_text)
        if page.revision is None or current_target is None or not _same_title(current_target, expected):
            record.add(_not_done(title, "redirect", "the page changed since the plan"))
            return
    _write_page(
        {"title": title, "action": "redirect", "target": target, "old_text": page.source_text},
        page,
        content,
        writer,
        record,
        summary=summary,
    )


def _redirect_target(text: str) -> str | None:
    match = _REDIRECT.match(text)
    return match.group(1) if match else None


def _same_title(left: str, right: str | None) -> bool:
    if right is None:
        return False

    def normal(title: str) -> str:
        title = " ".join(title.replace("_", " ").split())
        namespace, colon, name = title.partition(":")
        if colon and namespace.casefold() in ("file", "image"):
            title = f"File:{name.strip()[:1].upper()}{name.strip()[1:]}"
        return title

    return normal(left) == normal(right)


def _pending_write_evidence(
    entry: dict[str, Any], writer: PublishWriter, *, written: MediaWikiPageSnapshot | None = None
) -> dict[str, Any]:
    """Read proof of a committed request without replaying it or adopting an editor's revision."""
    title = str(entry["title"])
    reviewed = entry.get("reviewed_snapshot")
    text = entry.get("intended_source")
    model = entry.get("intended_content_model")
    account = entry.get("edit_account")
    if (
        not isinstance(reviewed, dict)
        or reviewed.get("title") != title
        or not isinstance(text, str)
        or hashlib.sha256(text.encode("utf-8")).hexdigest() != entry.get("intended_source_sha256")
        or not isinstance(model, str)
        or not model
        or not account
        or account != writer.edit_account
        or not entry.get("api_url")
        or entry["api_url"] != writer.api_url
    ):
        raise ValueError("the durable request source, model, account or endpoint is not proven")
    base = reviewed.get("revision")
    if base is not None and not isinstance(base, dict):
        raise ValueError("the reviewed revision is not proven")
    base_id = 0 if base is None else base.get("revision_id")
    page = written if written is not None else writer.get_page_snapshots([title])[title]
    revision = page.revision
    nochange = (
        written is not None
        and entry.get("verified") is True
        and entry.get("done") is False
        and not entry.get("pending_mutation")
        and revision is not None
        and revision.revision_id == base_id
    )
    if (
        page.title != title
        or revision is None
        or revision.title != title
        or revision.page_id <= 0
        or (revision.revision_id == base_id and not nochange)
        or (not nochange and revision.parent_revision_id != base_id)
        or revision.user != account
        or page.source_text is None
        or normalize_saved_text(page.source_text) != normalize_saved_text(text)
        or page.content_model != model
    ):
        raise ValueError("the pending edit's own-account revision, exact parent, source and model are not proven")
    parent = None
    if base is not None:
        if (
            type(base_id) is not int
            or base_id <= 0
            or base.get("title") != title
            or revision.page_id != base.get("page_id")
            or not isinstance(reviewed.get("source_text"), str)
            or reviewed.get("content_model") != model
        ):
            raise ValueError("the reviewed parent page, source or model is not proven")
        parent = writer.get_revision_snapshots([base_id])[base_id]
        if (
            parent.title != title
            or parent.revision is None
            or parent.revision.title != title
            or parent.revision.revision_id != base_id
            or parent.revision.page_id != revision.page_id
            or parent.source_text is None
            or normalize_saved_text(parent.source_text) != normalize_saved_text(reviewed["source_text"])
            or parent.content_model != model
        ):
            raise ValueError("the historical parent revision is not proven")
    elif reviewed.get("source_text") is not None:
        raise ValueError("the reviewed missing page is not proven")
    return {
        "done": True,
        "pending_mutation": False,
        "mutation_state": "reconciled",
        "verified": True,
        "revision": revision.revision_id,
        "written_snapshot": asdict(page),
        "actual_parent_snapshot": asdict(parent) if parent is not None else None,
        "requires_rollback": parent is not None,
    }


def _reconcile_pending_edits(run: RunRecord, writer: PublishWriter, record: RunRecord) -> bool:
    """Prove every ambiguous request read-only before undoing any known file or page mutation."""
    proven: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entry in run.entries:
        if not entry.get("pending_mutation"):
            continue
        try:
            evidence = _pending_write_evidence(entry, writer)
        except (MediaWikiAPIError, KeyError, ValueError) as error:
            record.add(_not_done(str(entry["title"]), f"reconcile {entry['action']}", str(error)))
            return False
        proven.append((entry, evidence))
    for entry, evidence in proven:
        run.update(entry, **evidence)
    return True


def _edit_endpoint_matches(entry: dict[str, Any], writer: PublishWriter, record: RunRecord) -> bool:
    if entry.get("api_url") and entry["api_url"] == writer.api_url:
        return True
    record.add(_not_done(str(entry["title"]), f"revert {entry['action']}", "the recorded wiki endpoint is not proven"))
    return False


def _resume_restorations(run: RunRecord, writer: PublishWriter, record: RunRecord) -> bool:
    """Attribute linked restoration requests before skipping a restored edit or undoing earlier files."""
    for entry in run.entries:
        if entry.get("restoration_record") is None:
            continue
        try:
            _resume_restoration(run, entry, writer)
        except (MediaWikiAPIError, OSError, KeyError, IndexError, TypeError, ValueError) as error:
            record.add(_not_done(str(entry["title"]), f"resume {entry['action']}", str(error)))
            return False
    return True


def _resume_restoration(run: RunRecord, entry: dict[str, Any], writer: PublishWriter) -> None:
    from pathlib import Path

    directory = entry["restoration_record"]
    index = entry.get("restoration_entry")
    if not isinstance(directory, str) or type(index) is not int or index < 0:
        raise ValueError("the original ledger's restoration reference is not proven")
    recovery = RunRecord.load(Path(directory))
    restored = recovery.entries[index]
    reviewed = restored.get("reviewed_snapshot")
    parent = entry.get("actual_parent_snapshot")
    written = entry.get("written_snapshot")
    if (
        restored.get("title") != entry["title"]
        or restored.get("action") != f"revert {entry['action']}"
        or not isinstance(reviewed, dict)
        or not isinstance(reviewed.get("revision"), dict)
        or reviewed["revision"].get("revision_id") != entry.get("revision")
        or not isinstance(parent, dict)
        or not isinstance(parent.get("source_text"), str)
        or not isinstance(written, dict)
        or not isinstance(written.get("revision"), dict)
        or reviewed["revision"].get("page_id") != written["revision"].get("page_id")
        or not isinstance(restored.get("intended_source"), str)
        or normalize_saved_text(restored["intended_source"]) != normalize_saved_text(parent["source_text"])
        or restored.get("intended_content_model") != parent.get("content_model")
        or restored.get("edit_account") != entry.get("edit_account")
    ):
        raise ValueError("the restoration request does not match the original acknowledged edit and actual parent")
    if restored.get("mutation_state") == "rejected":
        run.update(entry, restoration_record=None, restoration_entry=None)
        return
    if restored.get("requires_rollback"):
        raise ValueError("the linked restoration has an unresolved acknowledged verification failure")
    revision = restored.get("revision")
    if restored.get("pending_mutation"):
        evidence = _pending_write_evidence(restored, writer)
        revision = evidence["revision"]
        recovery.update(restored, **(evidence | {"requires_rollback": False}))
    else:
        if not restored.get("verified") or type(revision) is not int or revision <= 0:
            raise ValueError("the linked restoration revision is not proven")
        # A later upload or editor revision must not cause a completed page restoration to replay.
        snapshot = writer.get_revision_snapshots([revision])[revision]
        if snapshot.revision is None or snapshot.revision.revision_id != revision:
            raise ValueError("the linked historical restoration revision is not proven")
        _pending_write_evidence(restored, writer, written=snapshot)
    if entry.get("restoration_revision") is not None and entry["restoration_revision"] != revision:
        raise ValueError("the original ledger's restoration revision differs from its linked request")
    if entry.get("restoration_revision") != revision or entry.get("requires_rollback"):
        run.update(entry, restoration_revision=revision, requires_rollback=False)


def revert(
    run: RunRecord,
    writer: PublishWriter,
    administrator: AdministratorWriter | None,
    record: RunRecord,
    owners: Sequence[str],
    *,
    summary: str,
    titles: Sequence[str] | None = None,
) -> None:
    """Undo what a run changed.

    An update is undone by uploading the replaced bytes again, while the
    file's latest version is still the run's. A deleted copy is restored, and
    its description replaces the redirect that the run wrote at its title. An
    orphan is restored with its redirects. A changed redirect gets its earlier
    text back. Created files and created redirects stay and are listed. A moved
    file goes back to its old title without a redirect, after the redirects
    that named the old title name it again, so no redirect is left behind.

    Raises:
        ValueError: If the run moved or deleted something and no administrator is given.
    """
    if any(entry.get("pending_mutation") for entry in record.entries):
        raise ValueError("Resolve the recovery run's pending native edit before another write")
    for entry in run.entries:
        if (
            entry.get("reviewed_snapshot") is not None
            or (entry.get("done") and entry["action"] in ("redirect", "describe"))
        ) and not _edit_endpoint_matches(entry, writer, record):
            return
    if not _resume_restorations(run, writer, record):
        return
    if not _reconcile_pending_edits(run, writer, record):
        return
    done = [entry for entry in run.entries if entry.get("done") and (titles is None or entry["title"] in titles)]
    if administrator is None and any(entry["action"] in ("move", "retire", "orphan") for entry in done):
        raise ValueError("The run moved or deleted files, which only the administrator account undoes")
    restored = {str(entry["title"]) for entry in done if entry["action"] == "retire"}
    # Recover the actual overwritten parent before undoing earlier uploads or moves.
    for entry in done:
        if entry.get("requires_rollback") and not _restore_unverified_edit(
            entry, writer, record, summary, authority=run
        ):
            return
    for entry in done:
        title = str(entry["title"])
        action = entry["action"]
        if entry.get("requires_rollback") or entry.get("restoration_revision") is not None:
            continue
        if action == "update":
            _revert_update(entry, run.directory, writer, record, owners, summary=summary)
        elif action == "retire" and administrator is not None:
            _restore_copy(entry, writer, administrator, record, summary)
        elif action == "orphan" and administrator is not None:
            _restore_orphan(entry, administrator, record, summary)
        elif action == "redirect" and title in restored:
            continue
        elif action == "redirect" and entry.get("old_text") is not None:
            _restore_redirect(entry, writer, record, summary)
        elif action == "describe":
            _restore_description(entry, writer, record, summary)
        elif action in ("create", "redirect"):
            record.add({"title": title, "action": f"keep {action}", "done": False, "reason": "the run created it"})
    for entry in reversed(done):
        if entry["action"] == "move" and administrator is not None:
            _revert_move(entry, writer, administrator, record, summary)


def _revert_move(
    entry: dict[str, Any], writer: PublishWriter, administrator: AdministratorWriter, record: RunRecord, summary: str
) -> None:
    """Move a moved file back over the redirect that its move left, while both are as the run left them."""
    title, source = str(entry["title"]), str(entry["source"])
    current = _current(writer, title)
    left = writer.get_page_snapshots([source])[source].source_text
    if current is None or current.sha1 != entry["sha1"] or not _same_title(_redirect_target(left or "") or "", title):
        record.add({"title": title, "action": "revert move", "done": False, "reason": "the file changed since"})
        return
    try:
        administrator.move_page(title, source, summary, leave_redirect=False)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert move", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert move", "done": True, "source": source})
    _purge(administrator, (title, source))


def _revert_update(
    entry: dict[str, Any],
    run_directory: Path,
    writer: PublishWriter,
    record: RunRecord,
    owners: Sequence[str],
    *,
    summary: str,
) -> None:
    title = str(entry["title"])
    current = _current(writer, title)
    if current is None or current.sha1 != entry["new_sha1"] or current.user not in owners:
        record.add({"title": title, "action": "revert update", "done": False, "reason": "the file changed since"})
        return
    source = run_directory / str(entry["replaced"])
    if not source.is_file():
        record.add({"title": title, "action": "revert update", "done": False, "reason": "the replaced bytes are lost"})
        return
    name = title.removeprefix("File:")
    try:
        try:
            writer.upload_file(str(source), name, summary, ignore_warnings=False)
        except MediaWikiUploadWarningError as warning:
            if set(warning.warnings) - {"exists", "duplicate", "duplicateversions"} or warning.filekey is None:
                reason = f"MediaWiki warned: {', '.join(sorted(warning.warnings))}"
                record.add({"title": title, "action": "revert update", "done": False, "reason": reason})
                return
            writer.confirm_upload(warning.filekey, name, summary)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert update", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert update", "done": True, "sha1": entry["old_sha1"]})
    _purge(writer, (title,))


def _restore_copy(
    entry: dict[str, Any], writer: PublishWriter, administrator: AdministratorWriter, record: RunRecord, summary: str
) -> None:
    """Restore a deleted copy at its title, where the run left a redirect to the picture's file.

    Undeleting brings back the copy's file and its revisions, which are older
    than the redirect, so the redirect stays the page's text until the copy's
    description replaces it.
    """
    title = str(entry["title"])
    page = writer.get_page_snapshots([title])[title]
    if page.source_text is not None and not _same_title(_redirect_target(page.source_text) or "", str(entry["file"])):
        record.add({"title": title, "action": "revert retire", "done": False, "reason": "the page changed since"})
        return
    try:
        administrator.undelete_page(title, summary)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert retire", "done": False, "reason": str(error)})
        return
    restored = writer.get_page_snapshots([title])[title]
    if restored.revision is not None and entry.get("description") is not None:
        revision = _write_page(
            {"title": title, "action": "revert retire", "old_text": restored.source_text, "undeleted": True},
            restored,
            str(entry["description"]),
            writer,
            record,
            summary=summary,
        )
        if revision is None:
            return
    else:
        record.add({"title": title, "action": "revert retire", "done": True})
    _purge(administrator, (title,))


def _restore_orphan(entry: dict[str, Any], administrator: AdministratorWriter, record: RunRecord, summary: str) -> None:
    title = str(entry["title"])
    try:
        administrator.undelete_page(title, summary)
        for redirect in entry.get("redirects", ()):
            administrator.undelete_page(str(redirect), summary)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert orphan", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert orphan", "done": True})
    _purge(administrator, (title, *entry.get("redirects", ())))


def _restore_redirect(entry: dict[str, Any], writer: PublishWriter, record: RunRecord, summary: str) -> None:
    title = str(entry["title"])
    if not _edit_endpoint_matches(entry, writer, record):
        return
    page = writer.get_page_snapshots([title])[title]
    current = _redirect_target(page.source_text or "")
    if (
        page.revision is None
        or (entry.get("revision") is not None and page.revision.revision_id != entry["revision"])
        or current is None
        or not _same_title(current, str(entry["target"]))
    ):
        record.add({"title": title, "action": "revert redirect", "done": False, "reason": "the page changed since"})
        return
    _write_page(
        {"title": title, "action": "revert redirect", "old_text": page.source_text},
        page,
        str(entry["old_text"]),
        writer,
        record,
        summary=summary,
    )


def _restore_description(entry: dict[str, Any], writer: PublishWriter, record: RunRecord, summary: str) -> None:
    """Put a description page's earlier text back, while it still holds the description that the run wrote."""
    title = str(entry["title"])
    if not _edit_endpoint_matches(entry, writer, record):
        return
    page = writer.get_page_snapshots([title])[title]
    if (
        page.revision is None
        or (entry.get("revision") is not None and page.revision.revision_id != entry["revision"])
        or page.source_text is None
        or normalize_saved_text(page.source_text) != normalize_saved_text(str(entry["text"]))
    ):
        record.add({"title": title, "action": "revert describe", "done": False, "reason": "the page changed since"})
        return
    _write_page(
        {"title": title, "action": "revert describe", "old_text": page.source_text},
        page,
        str(entry["old_text"]),
        writer,
        record,
        summary=summary,
    )


def _restore_unverified_edit(
    entry: dict[str, Any],
    writer: PublishWriter,
    record: RunRecord,
    summary: str,
    *,
    authority: RunRecord | None = None,
) -> bool:
    """Restore only a proven actual parent while the acknowledged revision is still current."""
    title = str(entry["title"])
    action = f"revert {entry['action']}"
    if not _edit_endpoint_matches(entry, writer, record):
        return False
    parent = entry.get("actual_parent_snapshot")
    written = entry.get("written_snapshot")
    if not isinstance(parent, dict) or not isinstance(written, dict):
        record.add(_not_done(title, action, "the actual parent revision is not proven"))
        return False
    parent_revision = parent.get("revision")
    written_revision = written.get("revision")
    if (
        not isinstance(parent_revision, dict)
        or not isinstance(written_revision, dict)
        or not isinstance(parent.get("source_text"), str)
        or not isinstance(parent.get("content_model"), str)
        or not parent["content_model"]
        or parent.get("title") != title
        or written.get("title") != title
        or written_revision.get("revision_id") != entry["revision"]
        or written_revision.get("parent_revision_id") != parent_revision.get("revision_id")
        or written_revision.get("page_id") != parent_revision.get("page_id")
    ):
        record.add(_not_done(title, action, "the actual parent revision is not proven"))
        return False
    page = writer.get_page_snapshots([title])[title]
    if (
        page.revision is None
        or page.revision.revision_id != entry["revision"]
        or page.revision.page_id != written_revision["page_id"]
        or page.source_text is None
        or not isinstance(written.get("source_text"), str)
        or normalize_saved_text(page.source_text) != normalize_saved_text(written["source_text"])
        or page.content_model != written.get("content_model")
        or page.content_model != parent["content_model"]
    ):
        record.add(_not_done(title, action, "the acknowledged revision changed or its model cannot be restored"))
        return False
    revision = _write_page(
        {"title": title, "action": action, "old_text": page.source_text},
        page,
        parent["source_text"],
        writer,
        record,
        summary=summary,
        restoration_of=(authority, entry) if authority is not None else None,
    )
    return revision is not None
