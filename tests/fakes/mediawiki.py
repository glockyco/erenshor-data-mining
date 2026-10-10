"""The one stateful double for the MediaWiki client that every test replaces.

Arrange a scenario with `put_page`/`put_redirect`/`put_file`, or by setting the
per-title state a test needs to control directly (`embedded_in`,
`page_categories`, `category_members`, `linking_pages`, `wanted_pages`,
`parse_overrides`). Every write mutates the same state every read observes, so
a test asserts the resulting page or file rather than how the fake was
called.

Contract-tested against the local wiki in
`tests/contract/infrastructure/wiki/test_mediawiki_fake_contract.py`, so its
behavior cannot drift from what the real server does for the operations that
test covers.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from erenshor.application.services.image_publication import LiveWiki
from erenshor.infrastructure.wiki import (
    MediaWikiAssertionError,
    MediaWikiEditConflictError,
    MediaWikiFile,
    MediaWikiFilePages,
    MediaWikiFileVersion,
    MediaWikiNetworkError,
    MediaWikiPageRevision,
    MediaWikiPageSnapshot,
    MediaWikiParse,
    MediaWikiParsedLink,
    MediaWikiTitleStatus,
    MediaWikiUploadWarningError,
)

EditAssertion = Literal["user", "bot"]

_CATEGORY_LINK = re.compile(r"\[\[Category:([^\]|]+)(?:\|[^\]]*)?\]\]")

_DEFAULT_RIGHTS = frozenset(
    {"editinterface", "delete", "undelete", "movefile", "suppressredirect", "upload", "edit", "createpage"}
)


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()


@dataclass
class _FileVersion:
    data: bytes
    user: str
    comment: str


@dataclass
class MediaWikiFake:
    """One in-memory wiki: pages with revision history, files with version history,
    and the account currently editing them."""

    pages: dict[str, str] = field(default_factory=dict)
    revisions: dict[str, int] = field(default_factory=dict)
    page_ids: dict[str, int] = field(default_factory=dict)
    page_users: dict[str, str | None] = field(default_factory=dict)
    files: dict[str, list[_FileVersion]] = field(default_factory=dict)
    archive: dict[str, tuple[list[_FileVersion], str]] = field(default_factory=dict)
    used: set[str] = field(default_factory=set)
    warn: dict[str, dict[str, str]] = field(default_factory=dict)
    fail_after_uploads: int | None = None
    lose_move_answers: bool = False
    uploads: int = 0
    watched: tuple[str, ...] = ()
    dark: set[str] = field(default_factory=set)
    purged: list[tuple[str, ...]] = field(default_factory=list)
    edit_account: str | None = "ErenshorBot"
    is_bot: bool = True
    rights: frozenset[str] = field(default_factory=lambda: _DEFAULT_RIGHTS)
    embedded_in: dict[str, tuple[str, ...]] = field(default_factory=dict)
    page_categories: dict[str, frozenset[str]] = field(default_factory=dict)
    category_members: dict[str, tuple[str, ...]] = field(default_factory=dict)
    linking_pages: dict[str, tuple[str, ...]] = field(default_factory=dict)
    wanted_pages: tuple[str, ...] = ()
    direct_media: dict[str, bytes] = field(default_factory=dict)
    parse_overrides: dict[tuple[str, str | None], MediaWikiParse] = field(default_factory=dict)
    login_calls: int = 0
    _stash: dict[str, tuple[str, bytes, str]] = field(default_factory=dict)
    _next_page_id: int = 1000

    # --- Arranging a scenario ---

    def put_page(self, title: str, text: str, *, user: str | None = None) -> None:
        """Set a page's text as if an earlier edit had already landed; bumps its revision."""
        self._write_page(title, text, user)
        self._mark_dark()

    def put_redirect(self, title: str, target: str) -> None:
        self._write_page(title, f"#REDIRECT [[{target}]]", None)
        self._mark_dark()

    def put_file(self, title: str, data: bytes, *, user: str | None = None, comment: str = "Automated upload") -> None:
        uploader = user or self.edit_account or "ErenshorBot"
        self.files.setdefault(title, []).insert(0, _FileVersion(data, uploader, comment))
        if title not in self.pages:
            self._write_page(title, "An uploaded file.", user)
        self._mark_dark()

    def _write_page(self, title: str, text: str, user: str | None) -> None:
        self.pages[title] = text
        self.revisions[title] = self.revisions.get(title, 0) + 1
        self.page_ids.setdefault(title, self._next_id())
        self.page_users[title] = user or self.edit_account

    def _next_id(self) -> int:
        page_id = self._next_page_id
        self._next_page_id += 1
        return page_id

    @staticmethod
    def _target(text: str) -> str | None:
        return text.removeprefix("#REDIRECT [[").removesuffix("]]") if text.startswith("#REDIRECT [[") else None

    def _shows_a_picture(self, title: str) -> bool:
        target = self._target(self.pages.get(title, ""))
        return title in self.files or (target is not None and target in self.files)

    def _mark_dark(self) -> None:
        """A page that an operation left without a visible picture joins `dark`, once watched."""
        self.dark.update(title for title in self.watched if not self._shows_a_picture(title))

    # --- Guards shared by every write and by the reads that take `assertion` ---

    def _check_assertion(self, assertion: str | None, assert_user: str | None) -> None:
        if assertion == "bot" and not self.is_bot:
            raise MediaWikiAssertionError("Assertion failed: the current session is not flagged as a bot")
        if assertion in ("user", "bot") and self.edit_account is None:
            raise MediaWikiAssertionError("Assertion failed: no user is logged in")
        if assert_user is not None and assert_user != self.edit_account:
            raise MediaWikiAssertionError(
                f"Assertion failed: logged in as {self.edit_account!r}, expected {assert_user!r}"
            )

    # --- Session ---

    def login(self) -> None:
        self.login_calls += 1

    def close(self) -> None:
        pass

    def get_current_user_rights(
        self, assertion: EditAssertion = "user", assert_user: str | None = None
    ) -> frozenset[str]:
        self._check_assertion(assertion, assert_user)
        return self.rights

    # --- Page reads ---

    def get_page(self, title: str) -> str | None:
        return self.pages.get(title)

    def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]:
        return {title: self.pages.get(title) for title in titles}

    def get_page_categories(self, titles: Sequence[str]) -> dict[str, frozenset[str]]:
        return {title: self.page_categories.get(title, frozenset()) for title in titles}

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        if assertion is not None:
            self._check_assertion(assertion, assert_user)
        return self.embedded_in.get(title, ())

    def get_category_members(self, title: str, namespace: int = 0) -> tuple[str, ...]:
        return self.category_members.get(title, ())

    def get_linking_pages_by_title(self, titles: Sequence[str], namespace: int = 0) -> dict[str, tuple[str, ...]]:
        return {title: self.linking_pages.get(title, ()) for title in titles}

    def get_wanted_pages(self, namespace: int = 0) -> tuple[str, ...]:
        return self.wanted_pages

    def get_title_statuses(self, titles: Sequence[str]) -> dict[str, MediaWikiTitleStatus]:
        statuses = {}
        for title in titles:
            text = self.pages.get(title)
            target = self._target(text) if text is not None else None
            statuses[title] = MediaWikiTitleStatus(title, title, target, text is not None)
        return statuses

    def parse_wikitext(
        self,
        title: str,
        text: str,
        *,
        sandbox_title: str | None = None,
        sandbox_text: str | None = None,
        sandbox_content_model: str | None = None,
    ) -> MediaWikiParse:
        override = self.parse_overrides.get((title, sandbox_title))
        if override is not None:
            return override
        source = sandbox_text if sandbox_text is not None else text
        names = dict.fromkeys(name.strip() for name in _CATEGORY_LINK.findall(source))
        categories = tuple(MediaWikiParsedLink(f"Category:{name}", f"Category:{name}" in self.pages) for name in names)
        return MediaWikiParse(html=f"<p>{source}</p>", templates=(), categories=categories)

    def get_page_snapshots(
        self, titles: Sequence[str], assertion: EditAssertion | None = None, assert_user: str | None = None
    ) -> dict[str, MediaWikiPageSnapshot]:
        if assertion is not None:
            self._check_assertion(assertion, assert_user)
        snapshots = {}
        for title in titles:
            text = self.pages.get(title)
            revision = (
                MediaWikiPageRevision(
                    title,
                    self.page_ids.get(title, 0),
                    self.revisions[title],
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:01Z",
                    self.page_users.get(title),
                )
                if text is not None
                else None
            )
            snapshots[title] = MediaWikiPageSnapshot(title, text, revision, "2026-01-01T00:00:01Z")
        return snapshots

    def get_page_revision_metadata(
        self, title: str, assertion: EditAssertion | None = None, assert_user: str | None = None
    ) -> MediaWikiPageRevision | None:
        return self.get_page_snapshots((title,), assertion, assert_user)[title].revision

    # --- Interface-page reads (the narrower `InterfaceClient` protocol) ---

    def raw_page(self, title: str) -> str | None:
        return self.pages.get(title)

    def media_file(self, title: str) -> bytes | None:
        versions = self.files.get(title)
        return versions[0].data if versions else None

    def media_file_by_path(self, path: str) -> bytes | None:
        return self.direct_media.get(path)

    # --- File listing ---

    def list_files(self) -> tuple[MediaWikiFile, ...]:
        return tuple(self._listed_file(title) for title in self.files)

    def list_file_pages(self) -> MediaWikiFilePages:
        redirects = {title: target for title, text in self.pages.items() if (target := self._target(text)) is not None}
        pages = frozenset(title for title in self.pages if title not in redirects and title.startswith("File:"))
        return MediaWikiFilePages(redirects=redirects, pages=pages)

    def listing(self) -> LiveWiki:
        files = {title: self._listed_file(title) for title in self.files}
        redirects = {title: target for title, text in self.pages.items() if (target := self._target(text)) is not None}
        return LiveWiki(files, redirects, frozenset(title for title in self.pages if title not in redirects))

    def _listed_file(self, title: str) -> MediaWikiFile:
        latest = self.files[title][0]
        width, height = self._dimensions(latest.data)
        return MediaWikiFile(
            title,
            _sha1(latest.data),
            latest.user,
            latest.comment,
            len(latest.data),
            width,
            height,
            "2026-01-01T00:00:00Z",
            f"u:{title}",
        )

    @staticmethod
    def _dimensions(data: bytes) -> tuple[int, int]:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            return image.size

    def download(self, url: str) -> bytes:
        return self.files[url.removeprefix("u:")][0].data

    def is_file_used(self, title: str) -> bool:
        return title in self.used

    def get_file_versions(self, title: str, limit: int = 50) -> tuple[MediaWikiFileVersion, ...]:
        versions = self.files.get(title, [])[:limit]
        return tuple(
            MediaWikiFileVersion(_sha1(v.data), v.user, v.comment, "2026-01-01T00:00:00Z", f"u:{title}")
            for v in versions
        )

    # --- Page writes ---

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
        content_model: str | None = None,
    ) -> int:
        self._check_assertion(assertion, assert_user)
        if title in self.pages:
            raise MediaWikiEditConflictError(f"Lost create race while safely creating page {title!r}")
        self._write_page(title, content, self.edit_account)
        self._mark_dark()
        return self.revisions[title]

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
        content_model: str | None = None,
    ) -> int:
        self._check_assertion(assertion, assert_user)
        if self.revisions.get(title) != base_revision.revision_id:
            raise MediaWikiEditConflictError(f"Edit conflict while safely editing page {title!r}")
        self._write_page(title, content, self.edit_account)
        self._mark_dark()
        return self.revisions[title]

    # --- File writes ---

    def upload_file(
        self, file_path: str, filename: str, comment: str, text: str = "", ignore_warnings: bool = False
    ) -> dict[str, Any]:
        if self.fail_after_uploads is not None and self.uploads >= self.fail_after_uploads:
            raise KeyboardInterrupt
        title = f"File:{filename}"
        data = Path(file_path).read_bytes()
        warnings = dict(self.warn.get(title, {}))
        if title in self.files:
            warnings["exists"] = filename
            if any(_sha1(version.data) == _sha1(data) for version in self.files[title][1:]):
                warnings["duplicateversions"] = "an earlier version"
        if any(_sha1(versions[0].data) == _sha1(data) for other, versions in self.files.items() if other != title):
            warnings["duplicate"] = "another file"
        if warnings and not ignore_warnings:
            self._stash["key"] = (title, data, text)
            raise MediaWikiUploadWarningError(warnings, "key")
        self._store(title, data, comment, text)
        return {"result": "Success"}

    def confirm_upload(self, filekey: str, filename: str, comment: str, text: str = "") -> dict[str, Any]:
        title, data, stashed_text = self._stash.pop(filekey)
        if title != f"File:{filename}":
            raise MediaWikiUploadWarningError({"filenamemismatch": filename}, filekey)
        self._store(title, data, comment, stashed_text)
        return {"result": "Success"}

    def _store(self, title: str, data: bytes, comment: str, text: str) -> None:
        self.uploads += 1
        self.files.setdefault(title, []).insert(0, _FileVersion(data, self.edit_account or "ErenshorBot", comment))
        if title not in self.pages:
            self._write_page(title, text, self.edit_account)
        self._mark_dark()

    def move_page(self, from_title: str, to_title: str, reason: str, *, leave_redirect: bool = True) -> None:
        """Move a file and its page; MediaWiki moves over a page only when it is a one-revision redirect back."""
        if to_title in self.pages and not (
            self._target(self.pages[to_title]) == from_title and self.revisions[to_title] == 1
        ):
            raise MediaWikiEditConflictError(f"Lost move race: {to_title!r} already exists")
        if from_title in self.files:
            self.files[to_title] = self.files.pop(from_title)
        self.pages[to_title] = self.pages.pop(from_title)
        self.revisions[to_title] = self.revisions.pop(from_title)
        self.page_ids[to_title] = self.page_ids.pop(from_title, self._next_id())
        self.page_users[to_title] = self.page_users.pop(from_title, None)
        if leave_redirect:
            self._write_page(from_title, f"#REDIRECT [[{to_title}]]", self.edit_account)
        self._mark_dark()
        if self.lose_move_answers:
            raise MediaWikiNetworkError("Request timeout: The read operation timed out")

    # --- Deletions (the administrator's) ---

    def delete_page(self, title: str, reason: str) -> None:
        self.archive[title] = (self.files.pop(title, []), self.pages.pop(title))
        self.revisions.pop(title, None)
        self.page_ids.pop(title, None)
        self.page_users.pop(title, None)
        self._mark_dark()

    def undelete_page(self, title: str, reason: str) -> None:
        """Restore a deleted page; a newer page at the title keeps its text, as with MediaWiki's merge."""
        versions, text = self.archive.pop(title)
        if versions:
            self.files[title] = versions
        if title not in self.pages:
            self._write_page(title, text, self.edit_account)

    # --- CDN purge ---

    def purge_pages(
        self,
        titles: Sequence[str],
        force_link_update: bool = True,
        force_recursive_link_update: bool = False,
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        if assertion is not None:
            self._check_assertion(assertion, assert_user)
        titles = tuple(titles)
        self.purged.append(titles)
        return titles
