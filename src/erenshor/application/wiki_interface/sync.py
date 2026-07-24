"""Sync live MediaWiki interface pages for local preview validation."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from erenshor.infrastructure.wiki.rate_limit import MediaWikiRequestor

FIXED_INTERFACE_TITLES: tuple[str, ...] = (
    "MediaWiki:Common.css",
    "MediaWiki:Vector.css",
    "MediaWiki:Common.js",
    "MediaWiki:Vector.js",
    "MediaWiki:Gadgets-definition",
    "MediaWiki:Sidebar",
    "MediaWiki:Mainpage-description",
    "MediaWiki:Recentchanges",
    "MediaWiki:Randompage",
    "MediaWiki:Help-mediawiki",
)

FIXED_SKIN_ASSETS: tuple[str, ...] = (
    "/images/Site-logo.png",
    "/images/Site-favicon.ico",
)

GADGET_SOURCE_SUFFIXES = (".css", ".js", ".json", ".vue")
CSS_IMAGE_URL_PATTERN = re.compile(r"url\((?P<quote>['\"]?)(?P<url>/?images/[^)'\"]+)(?P=quote)\)")


class InterfaceClient(Protocol):
    """Readable MediaWiki interface page and media source."""

    def raw_page(self, title: str) -> str | None:
        """Return raw page content, or None when the page is missing."""

    def media_file(self, title: str) -> bytes | None:
        """Return media file bytes by File: title, or None when the file is missing."""

    def media_file_by_path(self, path: str) -> bytes | None:
        """Return media file bytes by upload path, or None when the path is missing."""


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
class MediaWikiInterfaceAsset:
    """One synced static asset referenced by interface CSS."""

    title: str
    path: Path
    content: bytes
    changed: bool


@dataclass(frozen=True)
class MissingInterfaceAsset:
    """One static asset referenced by CSS that could not be resolved live."""

    source_path: str
    file_title: str


@dataclass(frozen=True)
class InterfaceSyncResult:
    """Result of one interface sync pass."""

    pages: list[MediaWikiInterfacePage]
    assets: list[MediaWikiInterfaceAsset]
    missing_assets: list[MissingInterfaceAsset]

    @property
    def changed_pages(self) -> list[MediaWikiInterfacePage]:
        """Pages whose fetched content differs from the local mirror."""
        return [page for page in self.pages if page.changed]


class MediaWikiInterfaceClient:
    """Read raw MediaWiki interface pages and files through the live wiki."""

    def __init__(self, requestor: MediaWikiRequestor) -> None:
        self._requestor = requestor
        self._origin = requestor.api_url.removesuffix("/api.php")

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

    def media_file(self, title: str) -> bytes | None:
        """Return media file bytes by File: title, or None when the file is missing."""
        payload = self._requestor.get(
            {
                "action": "query",
                "prop": "imageinfo",
                "titles": title,
                "iiprop": "url",
            }
        )
        pages = payload.get("query", {}).get("pages", [])
        if not isinstance(pages, list) or not pages:
            return None
        page = pages[0]
        if not isinstance(page, dict) or page.get("missing") is True:
            return None
        imageinfo = page.get("imageinfo", [])
        if not isinstance(imageinfo, list) or not imageinfo:
            return None
        info = imageinfo[0]
        if not isinstance(info, dict):
            return None
        url = info.get("url")
        if not isinstance(url, str):
            return None
        return self._download_image_url(url)

    def media_file_by_path(self, path: str) -> bytes | None:
        """Return media file bytes by upload path, or None when the path is missing."""
        return self._download_image_url(f"{self._origin}/{path.removeprefix('/')}")

    def _download_image_url(self, url: str) -> bytes | None:
        response = self._requestor.download(url)
        if response.status_code != 200:
            return None
        if not response.content_type.startswith("image/"):
            return None
        return response.content


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


def sync_interface_pages(
    *,
    client: InterfaceClient,
    output_root: Path,
    dry_run: bool,
    image_root: Path | None = None,
) -> InterfaceSyncResult:
    """Fetch required live interface pages and write the local mirror."""
    titles = list(FIXED_INTERFACE_TITLES)
    pages: list[MediaWikiInterfacePage] = []

    for title in titles:
        page = _fetch_page(client, output_root, title)
        pages.append(page)
        if title == "MediaWiki:Gadgets-definition":
            titles.extend(gadget_source_titles(page.content))

    asset_root = image_root if image_root is not None else output_root.parent / "images"
    assets, missing_assets = _fetch_assets(client, asset_root, pages)

    if not dry_run:
        for page in pages:
            page.path.parent.mkdir(parents=True, exist_ok=True)
            page.path.write_text(page.content, encoding="utf-8")
        for asset in assets:
            asset.path.parent.mkdir(parents=True, exist_ok=True)
            asset.path.write_bytes(asset.content)

    return InterfaceSyncResult(pages=pages, assets=assets, missing_assets=missing_assets)


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


def _fetch_assets(
    client: InterfaceClient,
    image_root: Path,
    pages: list[MediaWikiInterfacePage],
) -> tuple[list[MediaWikiInterfaceAsset], list[MissingInterfaceAsset]]:
    assets: list[MediaWikiInterfaceAsset] = []
    missing_assets: list[MissingInterfaceAsset] = []
    seen_paths: set[Path] = set()
    for asset_path in FIXED_SKIN_ASSETS:
        image_path = skin_asset_path(asset_path)
        asset = _fetch_asset(client, image_root, image_path)
        if asset is None:
            missing_assets.append(
                MissingInterfaceAsset(source_path=image_path.source_path, file_title=image_path.file_title)
            )
        else:
            assets.append(asset)
            seen_paths.add(asset.path)

    for page in pages:
        if not page.title.endswith(".css"):
            continue
        for image_path in css_image_paths(page.content):
            local_path = image_root / image_path.relative_path
            if local_path in seen_paths:
                continue
            seen_paths.add(local_path)
            asset = _fetch_asset(client, image_root, image_path)
            if asset is None:
                missing_assets.append(
                    MissingInterfaceAsset(source_path=image_path.source_path, file_title=image_path.file_title)
                )
                continue
            assets.append(asset)
    return assets, missing_assets


def _fetch_asset(
    client: InterfaceClient,
    image_root: Path,
    image_path: CssImagePath,
) -> MediaWikiInterfaceAsset | None:
    local_path = image_root / image_path.relative_path
    content = client.media_file(image_path.file_title)
    if content is None:
        content = client.media_file_by_path(image_path.source_path)
    if content is None:
        return None
    previous = local_path.read_bytes() if local_path.exists() else b""
    return MediaWikiInterfaceAsset(
        title=image_path.file_title,
        path=local_path,
        content=content,
        changed=previous != content,
    )


def skin_asset_path(source_path: str) -> CssImagePath:
    relative_path = Path(source_path.removeprefix("/").removeprefix("images/"))
    return CssImagePath(
        source_path=source_path,
        relative_path=relative_path,
        file_title=f"File:{relative_path.name}",
    )


@dataclass(frozen=True)
class CssImagePath:
    """A local image path referenced by synced CSS."""

    source_path: str
    relative_path: Path
    file_title: str


def css_image_paths(css: str) -> list[CssImagePath]:
    """Return wiki image paths referenced by CSS url(...) expressions."""
    paths: list[CssImagePath] = []
    seen: set[Path] = set()
    for match in CSS_IMAGE_URL_PATTERN.finditer(css):
        raw_url = match.group("url").split("?", maxsplit=1)[0]
        relative = raw_url.removeprefix("/").removeprefix("images/")
        relative_path = Path(relative)
        if relative_path in seen:
            continue
        seen.add(relative_path)
        paths.append(
            CssImagePath(
                source_path=raw_url,
                relative_path=relative_path,
                file_title=f"File:{relative_path.name}",
            )
        )
    return paths


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
