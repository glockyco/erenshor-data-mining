"""Carrying out a publication plan and reverting a run (design D8 of rebuild-game-image-pipeline).

A run moves files first, then uploads, then writes redirects to the pictures'
files, then deletes each copy followed at once by the redirect that replaces
it, and deletes the orphans last. Before each write it reads the title again,
and it skips a title that changed since the plan, so the bot never replaces
something that someone else wrote meanwhile. An upload never ignores
MediaWiki's warnings up front: when the wiki answers only with warnings that
the verdict expects, the run confirms the stashed upload, and otherwise it
skips the title. The bot account moves, uploads, and edits; an administrator's
account with the delete grant deletes.

Every write goes to ``run.json`` the moment it happens, with the bytes that an
update replaced and the description of a deleted copy, so a stopped run loses
nothing and a later revert can restore what the run changed. A revert uploads
the replaced bytes again, restores deleted files, restores a redirect it
changed, and moves a moved file back without a redirect. Created files and
created redirects stay, and the revert lists them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from erenshor.infrastructure.wiki import MediaWikiAPIError, MediaWikiUploadWarningError

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

__all__ = ["PageDeleter", "PublishWriter", "RunRecord", "comment", "description", "execute", "move", "revert"]

_REDIRECT = re.compile(r"^\s*#REDIRECT\s*\[\[\s*:?\s*([^\]|]+?)\s*(?:\|[^\]]*)?\]\]", re.IGNORECASE)


class PublishWriter(Protocol):
    """The reads and writes of the bot account that a run needs."""

    def get_file_versions(self, title: str, limit: int = 50) -> tuple[MediaWikiFileVersion, ...]: ...

    def get_page_snapshots(self, titles: Sequence[str]) -> dict[str, MediaWikiPageSnapshot]: ...

    def is_file_used(self, title: str) -> bool: ...

    def download(self, url: str) -> bytes: ...

    def upload_file(
        self, file_path: str, filename: str, comment: str, text: str = "", ignore_warnings: bool = False
    ) -> dict[str, Any]: ...

    def confirm_upload(self, filekey: str, filename: str, comment: str, text: str = "") -> dict[str, Any]: ...

    def move_page(self, from_title: str, to_title: str, reason: str, *, leave_redirect: bool = True) -> None: ...

    def safe_create_page(self, title: str, content: str, start_timestamp: str, summary: str | None = None) -> int: ...

    def safe_edit_page(
        self, title: str, content: str, base_revision: MediaWikiPageRevision, summary: str | None = None
    ) -> int: ...


class PageDeleter(Protocol):
    """The deletions of an administrator's account that a run and its revert need."""

    def delete_page(self, title: str, reason: str) -> None: ...

    def undelete_page(self, title: str, reason: str) -> None: ...


def comment(picture: Picture, game_build: str) -> str:
    """The upload comment that records a picture's provenance."""
    return f"Game picture {picture.image_hash} ({picture.kind} from {picture.source}, game build {game_build})"


def description(picture: Picture, game_build: str) -> str:
    """The description page of a new file: how the picture was made, and the game's copyright notice."""
    if picture.kind == "portrait":
        made = (
            f"Rendered from the game's model (game build {picture.approved_build}, capture preset "
            f"{picture.capture_preset}) and approved after review. An in-game screenshot may replace it."
        )
    else:
        made = f"The game's icon, from the texture {picture.source} of game build {game_build}, unchanged."
    return f"== Summary ==\n{made}\n\n== Licensing ==\n{{{{License|Game}}}}\n"


@dataclass
class RunRecord:
    """The writes of one run, saved to ``run.json`` after each one."""

    directory: Path
    entries: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, directory: Path) -> RunRecord:
        path = directory / "run.json"
        entries = json.loads(path.read_text(encoding="utf-8"))["entries"] if path.is_file() else []
        return cls(directory, entries)

    def add(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "run.json"
        temporary = path.with_name(".run.json.tmp")
        temporary.write_text(json.dumps({"entries": self.entries}, indent=2, ensure_ascii=False) + "\n")
        temporary.replace(path)


def execute(
    plan: PublishPlan,
    catalog: Catalog,
    writer: PublishWriter,
    deleter: PageDeleter | None,
    record: RunRecord,
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
        ValueError: If the plan deletes and no deleter is given.
    """
    if plan.deletes and deleter is None:
        raise ValueError("The plan deletes copies or orphans, which needs the deletion account")
    missing_files: set[str] = set()
    followers: dict[str, list[PlannedTitle]] = {}
    for item in plan.titles:
        if item.verdict == "redirect" and item.redirect_target is not None:
            followers.setdefault(item.redirect_target, []).append(item)
    followed: set[str] = set()
    for item in plan.titles:
        if item.verdict != "move":
            continue
        if not move(item, writer, record, summary):
            missing_files.add(item.title)
            continue
        for follower in followers.get(str(item.source), ()):
            _redirect(follower, writer, record, summary)
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
            _redirect(item, writer, record, summary)
    if deleter is None:
        return
    for item in plan.titles:
        if item.verdict == "retire" and has_file(item) and _delete_copy(item, writer, deleter, record, summary):
            _redirect(item, writer, record, summary)
    for orphan in plan.orphans:
        _delete_orphan(orphan, writer, deleter, record, summary)


def _skipped(item: PlannedTitle, action: str, reason: str) -> dict[str, Any]:
    return {"title": item.title, "action": action, "done": False, "reason": reason}


def _describe(item: PlannedTitle, catalog: Catalog, writer: PublishWriter, record: RunRecord, summary: str) -> None:
    """Replace a redirect on the description page of the picture's file with the picture's description."""
    page = writer.get_page_snapshots([item.title])[item.title]
    current_target = _redirect_target(page.source_text or "")
    if page.revision is None or current_target is None or not _same_title(current_target, item.redirect_target):
        record.add(_skipped(item, "describe", "the page changed since the plan"))
        return
    text = description(catalog.pictures[item.image_hash], catalog.game_build)
    try:
        writer.safe_edit_page(item.title, text, page.revision, summary=summary)
    except MediaWikiAPIError as error:
        record.add(_skipped(item, "describe", f"the edit failed: {error}"))
        return
    record.add({"title": item.title, "action": "describe", "done": True, "text": text, "old_text": page.source_text})


def _current(writer: PublishWriter, title: str) -> MediaWikiFileVersion | None:
    versions = writer.get_file_versions(title, limit=1)
    return versions[0] if versions else None


def move(item: PlannedTitle, writer: PublishWriter, record: RunRecord, summary: str) -> bool:
    """Move the file at ``item.source`` to ``item.title`` with its history, leaving a redirect at the old title.

    The move goes ahead only while the old title holds the planned file and the
    new title has no page. Returns whether the new title holds the file.
    """
    source = str(item.source)
    current = _current(writer, source)
    if current is None or current.sha1 != item.source_sha1:
        record.add(_skipped(item, "move", f"the file at {source} changed since the plan"))
        return False
    page = writer.get_page_snapshots([item.title])[item.title]
    if page.source_text is not None or _current(writer, item.title) is not None:
        record.add(_skipped(item, "move", "the title gained a page since the plan"))
        return False
    try:
        writer.move_page(source, item.title, f"{summary}: {item.reason}")
    except MediaWikiAPIError as error:
        record.add(_skipped(item, "move", f"the move failed: {error}"))
        return False
    moved = _current(writer, item.title)
    record.add({"title": item.title, "action": "move", "done": True, "source": source, "sha1": item.source_sha1})
    if moved is None or moved.sha1 != item.source_sha1:
        record.add(_skipped(item, "move", "the moved file does not have the planned SHA-1"))
        return False
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
    text = description(picture, catalog.game_build)
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
    return True


def _delete_copy(
    item: PlannedTitle, writer: PublishWriter, deleter: PageDeleter, record: RunRecord, summary: str
) -> bool:
    current = _current(writer, item.title)
    if current is None or current.sha1 != item.live_sha1:
        record.add(_skipped(item, "retire", "the file changed since the plan"))
        return False
    page = writer.get_page_snapshots([item.title])[item.title]
    try:
        deleter.delete_page(item.title, f"{summary}: a copy of {item.file}, which holds the picture")
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
    return True


def _delete_orphan(
    orphan: Orphan, writer: PublishWriter, deleter: PageDeleter, record: RunRecord, summary: str
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
        deleter.delete_page(orphan.title, reason)
        for title in redirects:
            deleter.delete_page(title, reason)
    except MediaWikiAPIError as error:
        record.add(entry | {"reason": f"the deletion failed: {error}"})
        return
    record.add(entry | {"done": True, "sha1": current.sha1, "redirects": redirects})


def _redirect(item: PlannedTitle, writer: PublishWriter, record: RunRecord, summary: str) -> None:
    """Create the title's redirect to the picture's file, or point its redirect there.

    The page decides: the file history of a redirect title is its target's, so
    a file at the title shows as a page that is not a redirect.
    """
    content = f"#REDIRECT [[{item.file}]]"
    page = writer.get_page_snapshots([item.title])[item.title]
    try:
        if page.source_text is None:
            revision = writer.safe_create_page(item.title, content, page.start_timestamp, summary=summary)
            record.add({"title": item.title, "action": "redirect", "done": True, "target": item.file, "old_text": None})
            return
        current_target = _redirect_target(page.source_text)
        if page.revision is None or current_target is None or not _same_title(current_target, item.redirect_target):
            record.add(_skipped(item, "redirect", "the page changed since the plan"))
            return
        revision = writer.safe_edit_page(item.title, content, page.revision, summary=summary)
    except MediaWikiAPIError as error:
        record.add(_skipped(item, "redirect", f"the edit failed: {error}"))
        return
    record.add(
        {
            "title": item.title,
            "action": "redirect",
            "done": True,
            "target": item.file,
            "old_text": page.source_text,
            "revision": revision,
        }
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


def revert(
    run: RunRecord,
    writer: PublishWriter,
    deleter: PageDeleter | None,
    record: RunRecord,
    owners: Sequence[str],
    summary: str,
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
        ValueError: If the run deleted something and no deleter is given.
    """
    done = [entry for entry in run.entries if entry.get("done")]
    if deleter is None and any(entry["action"] in ("retire", "orphan") for entry in done):
        raise ValueError("The run deleted copies or orphans, which only the deletion account restores")
    restored = {str(entry["title"]) for entry in done if entry["action"] == "retire"}
    for entry in done:
        title = str(entry["title"])
        action = entry["action"]
        if action == "update":
            _revert_update(entry, run.directory, writer, record, owners, summary)
        elif action == "retire" and deleter is not None:
            _restore_copy(entry, writer, deleter, record, summary)
        elif action == "orphan" and deleter is not None:
            _restore_orphan(entry, deleter, record, summary)
        elif action == "redirect" and title in restored:
            continue
        elif action == "redirect" and entry.get("old_text") is not None:
            _restore_redirect(entry, writer, record, summary)
        elif action == "describe":
            _restore_description(entry, writer, record, summary)
        elif action in ("create", "redirect"):
            record.add({"title": title, "action": f"keep {action}", "done": False, "reason": "the run created it"})
    for entry in reversed(done):
        if entry["action"] == "move":
            _revert_move(entry, writer, record, summary)


def _revert_move(entry: dict[str, Any], writer: PublishWriter, record: RunRecord, summary: str) -> None:
    """Move a moved file back over the redirect that its move left, while both are as the run left them."""
    title, source = str(entry["title"]), str(entry["source"])
    current = _current(writer, title)
    left = writer.get_page_snapshots([source])[source].source_text
    if current is None or current.sha1 != entry["sha1"] or not _same_title(_redirect_target(left or "") or "", title):
        record.add({"title": title, "action": "revert move", "done": False, "reason": "the file changed since"})
        return
    try:
        writer.move_page(title, source, summary, leave_redirect=False)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert move", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert move", "done": True, "source": source})


def _revert_update(
    entry: dict[str, Any],
    run_directory: Path,
    writer: PublishWriter,
    record: RunRecord,
    owners: Sequence[str],
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


def _restore_copy(
    entry: dict[str, Any], writer: PublishWriter, deleter: PageDeleter, record: RunRecord, summary: str
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
        deleter.undelete_page(title, summary)
        restored = writer.get_page_snapshots([title])[title]
        if restored.revision is not None and entry.get("description") is not None:
            writer.safe_edit_page(title, str(entry["description"]), restored.revision, summary=summary)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert retire", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert retire", "done": True})


def _restore_orphan(entry: dict[str, Any], deleter: PageDeleter, record: RunRecord, summary: str) -> None:
    title = str(entry["title"])
    try:
        deleter.undelete_page(title, summary)
        for redirect in entry.get("redirects", ()):
            deleter.undelete_page(str(redirect), summary)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert orphan", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert orphan", "done": True})


def _restore_redirect(entry: dict[str, Any], writer: PublishWriter, record: RunRecord, summary: str) -> None:
    title = str(entry["title"])
    page = writer.get_page_snapshots([title])[title]
    current = _redirect_target(page.source_text or "")
    if page.revision is None or current is None or not _same_title(current, str(entry["target"])):
        record.add({"title": title, "action": "revert redirect", "done": False, "reason": "the page changed since"})
        return
    try:
        writer.safe_edit_page(title, str(entry["old_text"]), page.revision, summary=summary)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert redirect", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert redirect", "done": True})


def _restore_description(entry: dict[str, Any], writer: PublishWriter, record: RunRecord, summary: str) -> None:
    """Put a description page's earlier text back, while it still holds the description that the run wrote."""
    title = str(entry["title"])
    page = writer.get_page_snapshots([title])[title]
    if page.revision is None or page.source_text != entry["text"]:
        record.add({"title": title, "action": "revert describe", "done": False, "reason": "the page changed since"})
        return
    try:
        writer.safe_edit_page(title, str(entry["old_text"]), page.revision, summary=summary)
    except MediaWikiAPIError as error:
        record.add({"title": title, "action": "revert describe", "done": False, "reason": str(error)})
        return
    record.add({"title": title, "action": "revert describe", "done": True})
