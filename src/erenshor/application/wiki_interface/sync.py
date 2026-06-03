"""Sync live MediaWiki interface pages for local preview validation."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestor, MediaWikiRequestPolicy

FIXED_INTERFACE_TITLES: tuple[str, ...] = (
    "MediaWiki:Common.css",
    "MediaWiki:Vector.css",
    "MediaWiki:Common.js",
    "MediaWiki:Vector.js",
    "MediaWiki:Gadgets-definition",
)

GADGET_SOURCE_SUFFIXES = (".css", ".js", ".json", ".vue")


class InterfaceClient(Protocol):
    """Readable MediaWiki interface page source."""

    def raw_page(self, title: str) -> str | None:
        """Return raw page content, or None when the page is missing."""


class MissingInterfacePageError(RuntimeError):
    """Raised when a required live interface page is absent."""


@dataclass(frozen=True)
class MediaWikiInterfacePage:
    """One synced MediaWiki interface page."""

    title: str
    path: Path
    content: str
    diff: str
    changed: bool


@dataclass(frozen=True)
class InterfaceSyncResult:
    """Result of one interface sync pass."""

    pages: list[MediaWikiInterfacePage]

    @property
    def changed_pages(self) -> list[MediaWikiInterfacePage]:
        """Pages whose fetched content differs from the local mirror."""
        return [page for page in self.pages if page.changed]


class MediaWikiInterfaceClient:
    """Read raw MediaWiki interface page content through the Action API."""

    def __init__(self, *, api_url: str, rate_limit_delay: float = 1.0) -> None:
        self._requestor = MediaWikiRequestor(
            api_url=api_url,
            policy=MediaWikiRequestPolicy(read_delay=rate_limit_delay),
        )

    def close(self) -> None:
        """Close the owned HTTP client."""
        self._requestor.close()

    def raw_page(self, title: str) -> str | None:
        """Return raw page content, or None when the page is missing."""
        payload = self._requestor.get(
            {
                "action": "query",
                "prop": "revisions",
                "titles": title,
                "rvprop": "content",
                "rvslots": "main",
            }
        )
        main: object = None
        pages = payload.get("query", {}).get("pages", [])
        if isinstance(pages, list) and pages:
            page = pages[0]
            if isinstance(page, dict) and page.get("missing") is not True:
                revisions = page.get("revisions", [])
                if isinstance(revisions, list) and revisions:
                    revision = revisions[0]
                    if isinstance(revision, dict):
                        slots = revision.get("slots", {})
                        if isinstance(slots, dict):
                            main = slots.get("main")
        if isinstance(main, dict):
            content = main.get("content")
            if isinstance(content, str):
                return content
        return None


def gadget_source_titles(definition: str) -> list[str]:
    """Return MediaWiki:Gadget-* source page titles referenced by a gadget definition."""
    titles: list[str] = []
    seen: set[str] = set()
    for raw_line in definition.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("*"):
            continue
        for token in line.split("|")[1:]:
            source = token.strip()
            if not source.endswith(GADGET_SOURCE_SUFFIXES):
                continue
            title = f"MediaWiki:Gadget-{source}"
            if title not in seen:
                seen.add(title)
                titles.append(title)
    return titles


def interface_path(output_root: Path, title: str) -> Path:
    """Map a MediaWiki namespace title to its local mirror path."""
    if not title.startswith("MediaWiki:"):
        raise ValueError(f"interface title must be in MediaWiki namespace: {title}")
    filename = title.removeprefix("MediaWiki:").replace("/", "__")
    return output_root / "MediaWiki" / filename


def sync_interface_pages(*, client: InterfaceClient, output_root: Path, dry_run: bool) -> InterfaceSyncResult:
    """Fetch required live interface pages and write the local mirror."""
    titles = list(FIXED_INTERFACE_TITLES)
    pages: list[MediaWikiInterfacePage] = []

    for title in titles:
        page = _fetch_page(client, output_root, title)
        pages.append(page)
        if title == "MediaWiki:Gadgets-definition":
            titles.extend(gadget_source_titles(page.content))

    if not dry_run:
        for page in pages:
            page.path.parent.mkdir(parents=True, exist_ok=True)
            page.path.write_text(page.content, encoding="utf-8")

    return InterfaceSyncResult(pages=pages)


def _fetch_page(client: InterfaceClient, output_root: Path, title: str) -> MediaWikiInterfacePage:
    content = client.raw_page(title)
    if content is None:
        raise MissingInterfacePageError(f"Required MediaWiki interface page is missing: {title}")
    path = interface_path(output_root, title)
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    diff = _content_diff(output_root, path, previous, content)
    return MediaWikiInterfacePage(
        title=title,
        path=path,
        content=content,
        diff=diff,
        changed=previous != content,
    )


def _content_diff(output_root: Path, path: Path, previous: str, current: str) -> str:
    if previous == current:
        return ""
    display_path = (Path("wiki-dev/interface") / path.relative_to(output_root)).as_posix()
    return "".join(
        difflib.unified_diff(
            previous.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile=display_path,
            tofile=display_path,
        )
    )
