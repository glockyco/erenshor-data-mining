#!/usr/bin/env python3
"""Import repository-owned wiki pages into a local MediaWiki instance.

This helper is intentionally small and explicit. It is for the local dev wiki,
not production deployment. Production interface pages use the dedicated guarded
interface-deploy path rather than this local importer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

import httpx

from erenshor.application.wiki_interface.gadgets import (
    GadgetSpec,
    gadget_source_pages,
    load_gadget_spec,
    reconcile_definition,
)

MANIFEST_SCHEMA_VERSION = 1
MANIFEST_RELATIVE_PATH = Path("wiki-dev/runtime/import_pages.manifest.json")
REMOTE_QUERY_BATCH_SIZE = 50
CONTENT_MODELS = frozenset({"css", "javascript", "json", "Scribunto", "vue", "wikitext"})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

REQUIRED_INTERFACE_FILES = frozenset(
    {
        "Common.css",
        "Vector.css",
        "Common.js",
        "Vector.js",
        "Gadgets-definition",
        "Sidebar",
        "Mainpage-description",
        "Recentchanges",
        "Randompage",
        "Help-mediawiki",
    }
)


class PageSource(NamedTuple):
    """A local file and the MediaWiki page title it represents."""

    title: str
    path: Path
    content: str | None = None
    content_model: str = "wikitext"


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """Deterministic local identity for one managed MediaWiki page."""

    source_path: str
    content_model: str
    sha256: str


@dataclass(frozen=True, slots=True)
class RemotePage:
    """Current main-slot state for one queried MediaWiki page."""

    content: str
    content_model: str


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Observable mutations and no-op decisions from one reconciliation."""

    created: tuple[str, ...]
    updated: tuple[str, ...]
    unchanged: tuple[str, ...]
    deleted: tuple[str, ...]
    purged: tuple[str, ...]


def manifest_path(root: Path) -> Path:
    """Return the persistent local state path for managed imports."""
    return root / MANIFEST_RELATIVE_PATH


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


def _load_gadget_spec(root: Path) -> GadgetSpec | None:
    """Load the repository gadget allowlist when this root has one."""
    spec_path = root / "wiki" / "gadgets" / "gadgets.toml"
    return load_gadget_spec(root) if spec_path.is_file() else None


def _discover_gadget_pages(root: Path, spec: GadgetSpec) -> list[PageSource]:
    """Map allowlisted gadget sources to local MediaWiki page sources."""
    return [
        PageSource(
            title=source.title,
            path=root / source.source_path,
            content_model=source.content_model,
        )
        for source in gadget_source_pages(spec, root)
    ]


def discover_pages(root: Path, *, include_clean_dependencies: bool = False) -> list[PageSource]:
    """Discover interface, gadget, module, template, and fixture pages."""
    spec = _load_gadget_spec(root)
    pages: list[PageSource] = []
    definition_pages: list[PageSource] = []

    interface_pages = discover_interface_pages(root, spec=spec)
    if spec is None:
        pages.extend(interface_pages)
    else:
        for page in interface_pages:
            if page.title == "MediaWiki:Gadgets-definition":
                definition_pages.append(page)
            else:
                pages.append(page)
        pages.extend(_discover_gadget_pages(root, spec))

    modules_dir = root / "wiki" / "modules"
    if modules_dir.exists():
        for path in sorted(modules_dir.rglob("*.lua")):
            relative = path.relative_to(modules_dir).with_suffix("")
            title = "Module:" + "/".join(relative.parts)
            pages.append(PageSource(title=title, path=path, content_model="Scribunto"))

    fixture_modules_dir = root / "wiki-dev" / "fixtures" / "modules"
    if fixture_modules_dir.exists():
        fixture_paths = sorted(
            fixture_modules_dir.rglob("*.lua"),
            key=lambda path: (len(path.relative_to(fixture_modules_dir).parts), path.as_posix()),
        )
        for path in fixture_paths:
            relative = path.relative_to(fixture_modules_dir).with_suffix("")
            title = "Module:" + "/".join(relative.parts)
            pages.append(PageSource(title=title, path=path, content_model="Scribunto"))

    templates_dir = root / "wiki" / "templates"
    if templates_dir.exists():
        for path in sorted(templates_dir.rglob("*.wiki")):
            relative = path.relative_to(templates_dir).with_suffix("")
            title = "Template:" + "/".join(relative.parts).replace("_", " ")
            pages.append(PageSource(title=title, path=path))

    dependency_templates_dir = root / "wiki-dev" / "fixtures" / "dependencies" / "templates"
    if include_clean_dependencies and dependency_templates_dir.exists():
        for path in sorted(dependency_templates_dir.rglob("*.wiki")):
            relative = path.relative_to(dependency_templates_dir).with_suffix("")
            title = "Template:" + "/".join(relative.parts).replace("_", " ")
            pages.append(PageSource(title=title, path=path))

    fixture_pages_dir = root / "wiki-dev" / "fixtures" / "pages"
    if fixture_pages_dir.exists():
        for path in sorted(fixture_pages_dir.rglob("*.wiki")):
            relative = path.relative_to(fixture_pages_dir).with_suffix("")
            title = "/".join(relative.parts).replace("_", " ")
            pages.append(PageSource(title=title, path=path))

    pages.extend(definition_pages)
    return pages


def _interface_content_model(path: Path) -> str:
    """Infer the explicit MediaWiki content model for an interface source."""
    if path.suffix == ".css":
        return "css"
    if path.suffix == ".js":
        return "javascript"
    return "wikitext"


def discover_interface_pages(root: Path, *, spec: GadgetSpec | None = None) -> list[PageSource]:
    """Discover synced live interface pages for local preview.

    Managed gadget source pages are omitted because they are imported directly
    from ``wiki/gadgets`` in allowlist order by :func:`discover_pages`.
    """
    if spec is None:
        spec = _load_gadget_spec(root)
    interface_dir = root / "wiki-dev" / "interface" / "MediaWiki"
    if not interface_dir.exists():
        raise RuntimeError(
            "Local MediaWiki interface mirror is missing. "
            "Run `uv run erenshor wiki sync-interface` before importing local pages."
        )

    existing_files = {path.name for path in interface_dir.iterdir() if path.is_file()}
    missing_files = sorted(REQUIRED_INTERFACE_FILES - existing_files)
    if missing_files:
        missing = ", ".join(missing_files)
        raise RuntimeError(
            f"Local MediaWiki interface mirror is incomplete ({missing}). "
            "Run `uv run erenshor wiki sync-interface` before importing local pages."
        )

    theme_css_path = root / "wiki-dev" / "interface" / "theme-shim.css"
    theme_css = theme_css_path.read_text(encoding="utf-8") if theme_css_path.exists() else ""
    theme_js_path = root / "wiki-dev" / "interface" / "theme-shim.js"
    theme_js = theme_js_path.read_text(encoding="utf-8") if theme_js_path.exists() else ""

    managed_titles = {source.title for source in gadget_source_pages(spec, root)} if spec is not None else set()

    pages: list[PageSource] = []
    for path in sorted(interface_dir.iterdir()):
        if not path.is_file():
            continue
        title = "MediaWiki:" + path.name.replace("__", "/")
        if title in managed_titles:
            continue
        content = None
        if path.name == "Common.css" and theme_css:
            content = theme_css + "\n" + path.read_text(encoding="utf-8")
        if path.name == "Common.js" and theme_js:
            content = theme_js + "\n" + path.read_text(encoding="utf-8")
        if path.name == "Gadgets-definition" and spec is not None:
            content = reconcile_definition(path.read_text(encoding="utf-8"), spec)
        pages.append(
            PageSource(
                title=title,
                path=path,
                content=content,
                content_model=_interface_content_model(path),
            )
        )
    return pages


def login(client: httpx.Client, endpoint: str, username: str, password: str) -> None:
    """Log in to MediaWiki using the classic token flow."""
    token_response = client.get(
        endpoint,
        params={
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json",
        },
    )
    token_response.raise_for_status()
    login_token = str(token_response.json()["query"]["tokens"]["logintoken"])

    login_response = client.post(
        endpoint,
        data={
            "action": "login",
            "lgname": username,
            "lgpassword": password,
            "lgtoken": login_token,
            "format": "json",
        },
    )
    login_response.raise_for_status()
    result = login_response.json()["login"]["result"]
    if result != "Success":
        raise RuntimeError(f"MediaWiki login failed: {result}")


def csrf_token(client: httpx.Client, endpoint: str) -> str:
    """Fetch a CSRF token for edit operations."""
    response = client.get(
        endpoint,
        params={
            "action": "query",
            "meta": "tokens",
            "format": "json",
        },
    )
    response.raise_for_status()
    return str(response.json()["query"]["tokens"]["csrftoken"])


def page_content(page: PageSource) -> str:
    """Return the text to import for a local page source."""
    return page.content if page.content is not None else page.path.read_text(encoding="utf-8")


def _normalize_mediawiki_content(content: str) -> str:
    """Match TextContent.normalizeLineEndings before comparing stored text."""
    trimmed = content.rstrip(" \n\r\t\v\0")
    return trimmed.replace("\r\n", "\n").replace("\r", "\n")


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_manifest(root: Path, pages: Sequence[PageSource]) -> dict[str, ManifestEntry]:
    """Build a strict title-keyed manifest from the current managed sources."""
    resolved_root = root.resolve()
    manifest: dict[str, ManifestEntry] = {}
    for page in pages:
        if not page.title:
            raise ValueError("Managed page title must not be empty")
        if page.title in manifest:
            raise ValueError(f"Duplicate managed page title: {page.title}")
        if page.content_model not in CONTENT_MODELS:
            raise ValueError(f"Unsupported content model for {page.title}: {page.content_model}")
        try:
            source_path = page.path.resolve().relative_to(resolved_root).as_posix()
        except ValueError as exc:
            raise ValueError(f"Managed source is outside repository root: {page.path}") from exc
        manifest[page.title] = ManifestEntry(
            source_path=source_path,
            content_model=page.content_model,
            sha256=_content_sha256(page_content(page)),
        )
    return dict(sorted(manifest.items()))


def _validate_manifest_entry(title: str, value: object) -> ManifestEntry:
    if not isinstance(value, dict) or set(value) != {"source_path", "content_model", "sha256"}:
        raise ValueError(f"Invalid managed import manifest entry for {title!r}")
    source_path = value["source_path"]
    content_model = value["content_model"]
    sha256 = value["sha256"]
    if not isinstance(source_path, str) or not source_path or Path(source_path).is_absolute():
        raise ValueError(f"Invalid source path for {title!r}")
    if ".." in Path(source_path).parts:
        raise ValueError(f"Invalid source path for {title!r}")
    if not isinstance(content_model, str) or content_model not in CONTENT_MODELS:
        raise ValueError(f"Invalid content model for {title!r}")
    if not isinstance(sha256, str) or _SHA256_PATTERN.fullmatch(sha256) is None:
        raise ValueError(f"Invalid SHA-256 for {title!r}")
    return ManifestEntry(source_path=source_path, content_model=content_model, sha256=sha256)


def load_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Load the prior managed state, failing closed on malformed content."""
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError(f"Managed import manifest must not be a symlink: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid managed import manifest: {path}") from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "pages"}:
        raise ValueError(f"Invalid managed import manifest: {path}")
    if payload["schema_version"] != MANIFEST_SCHEMA_VERSION or not isinstance(payload["pages"], dict):
        raise ValueError(f"Unsupported managed import manifest: {path}")
    entries: dict[str, ManifestEntry] = {}
    for title, value in payload["pages"].items():
        if not isinstance(title, str) or not title:
            raise ValueError(f"Invalid managed page title in manifest: {title!r}")
        entries[title] = _validate_manifest_entry(title, value)
    return dict(sorted(entries.items()))


def _manifest_bytes(entries: Mapping[str, ManifestEntry]) -> bytes:
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "pages": {
            title: {
                "source_path": entry.source_path,
                "content_model": entry.content_model,
                "sha256": entry.sha256,
            }
            for title, entry in sorted(entries.items())
        },
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_manifest(path: Path, entries: Mapping[str, ManifestEntry]) -> None:
    """Atomically persist managed state without rewriting identical bytes."""
    data = _manifest_bytes(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Managed import manifest must not be a symlink: {path}")
    if path.is_file() and path.read_bytes() == data:
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary_path.unlink(missing_ok=True)


def edit_page(
    client: httpx.Client,
    endpoint: str,
    token: str,
    page: PageSource,
    summary: str,
    *,
    create_only: bool,
) -> None:
    """Create or update one managed page under an explicit race guard."""
    data = {
        "action": "edit",
        "title": page.title,
        "text": page_content(page),
        "summary": summary,
        "token": token,
        "format": "json",
    }
    if create_only:
        data["createonly"] = "1"
        data["contentmodel"] = page.content_model
    else:
        data["nocreate"] = "1"
    response = client.post(endpoint, data=data)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Edit failed for {page.title}: {payload['error']}")
    result = payload.get("edit", {}).get("result")
    if result != "Success":
        raise RuntimeError(f"Edit failed for {page.title}: {payload}")


def delete_page(client: httpx.Client, endpoint: str, token: str, title: str) -> None:
    """Delete one title that was owned by the prior managed manifest."""
    response = client.post(
        endpoint,
        data={
            "action": "delete",
            "title": title,
            "reason": "Remove absent local dev wiki page",
            "token": token,
            "format": "json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload or payload.get("delete", {}).get("title") != title:
        raise RuntimeError(f"Delete failed for {title}: {payload}")


def purge_page(client: httpx.Client, endpoint: str, token: str, title: str) -> None:
    """Purge one page so local smoke parses do not reuse stale parser output."""
    response = client.post(
        endpoint,
        data={
            "action": "purge",
            "titles": title,
            "forcelinkupdate": "1",
            "token": token,
            "format": "json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Purge failed for {title}: {payload['error']}")


def query_remote_pages(
    client: httpx.Client,
    endpoint: str,
    titles: Sequence[str],
) -> dict[str, RemotePage | None]:
    """Fetch exact main-slot content and models for managed titles in batches."""
    requested = tuple(dict.fromkeys(titles))
    remote: dict[str, RemotePage | None] = {}
    canonical_owners: dict[str, str] = {}
    for offset in range(0, len(requested), REMOTE_QUERY_BATCH_SIZE):
        batch = requested[offset : offset + REMOTE_QUERY_BATCH_SIZE]
        response = client.get(
            endpoint,
            params={
                "action": "query",
                "titles": "|".join(batch),
                "prop": "revisions",
                "rvprop": "content|contentmodel",
                "rvslots": "main",
                "format": "json",
                "formatversion": "2",
            },
        )
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict) or "error" in payload or not isinstance(payload.get("query"), dict):
            raise RuntimeError(f"Managed page query failed: {payload}")
        query = payload["query"]
        normalized: dict[str, str] = {}
        for item in query.get("normalized", []):
            if isinstance(item, dict) and isinstance(item.get("from"), str) and isinstance(item.get("to"), str):
                normalized[item["from"]] = item["to"]
        pages = query.get("pages")
        if not isinstance(pages, list):
            raise RuntimeError(f"Managed page query returned no pages: {payload}")
        by_canonical_title: dict[str, RemotePage | None] = {}
        for raw_page in pages:
            if not isinstance(raw_page, dict) or not isinstance(raw_page.get("title"), str):
                raise RuntimeError(f"Managed page query returned an invalid page: {raw_page}")
            title = raw_page["title"]
            if raw_page.get("missing") is True:
                by_canonical_title[title] = None
                continue
            revisions = raw_page.get("revisions")
            if not isinstance(revisions, list) or len(revisions) != 1:
                raise RuntimeError(f"Managed page query returned invalid revisions for {title}")
            revision = revisions[0]
            slots = revision.get("slots") if isinstance(revision, dict) else None
            main_slot = slots.get("main") if isinstance(slots, dict) else None
            if (
                not isinstance(main_slot, dict)
                or not isinstance(main_slot.get("content"), str)
                or not isinstance(main_slot.get("contentmodel"), str)
            ):
                raise RuntimeError(f"Managed page query returned an invalid main slot for {title}")
            by_canonical_title[title] = RemotePage(
                content=main_slot["content"],
                content_model=main_slot["contentmodel"],
            )
        for title in batch:
            canonical_title = normalized.get(title, title)
            owner = canonical_owners.setdefault(canonical_title, title)
            if owner != title:
                raise RuntimeError(f"Managed page titles normalize to the same title: {owner!r} and {title!r}")
            if canonical_title not in by_canonical_title:
                raise RuntimeError(f"Managed page query omitted {title}")
            if title in remote:
                raise RuntimeError(f"Managed page title normalizes ambiguously: {title}")
            remote[title] = by_canonical_title[canonical_title]
    return remote


def reconcile_pages(
    client: httpx.Client,
    endpoint: str,
    token: str,
    pages: Sequence[PageSource],
    root: Path,
    manifest_file: Path | None = None,
) -> ImportReport:
    """Reconcile managed local sources without touching unmanaged wiki pages."""
    state_path = manifest_file if manifest_file is not None else manifest_path(root)
    previous = load_manifest(state_path)
    current = build_manifest(root, pages)
    current_titles = tuple(page.title for page in pages)
    queried_titles = current_titles + tuple(title for title in previous if title not in current)
    remote = query_remote_pages(client, endpoint, queried_titles)

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    deleted: list[str] = []
    purge_titles: list[str] = []

    for page in pages:
        title = page.title
        entry = current[title]
        remote_page = remote[title]
        if remote_page is None:
            edit_page(client, endpoint, token, page, "Create local dev wiki page", create_only=True)
            created.append(title)
            purge_titles.append(title)
            continue
        if remote_page.content_model != entry.content_model:
            raise RuntimeError(
                f"Managed page content model mismatch for {title}: "
                f"expected {entry.content_model}, found {remote_page.content_model}"
            )
        expected_content = page_content(page)
        if _normalize_mediawiki_content(remote_page.content) != _normalize_mediawiki_content(expected_content):
            edit_page(client, endpoint, token, page, "Update local dev wiki page", create_only=False)
            updated.append(title)
            purge_titles.append(title)
        else:
            unchanged.append(title)

    for title in sorted(set(previous) - set(current)):
        if remote[title] is not None:
            delete_page(client, endpoint, token, title)
            deleted.append(title)

    for title in purge_titles:
        purge_page(client, endpoint, token, title)

    write_manifest(state_path, current)
    return ImportReport(
        created=tuple(created),
        updated=tuple(updated),
        unchanged=tuple(unchanged),
        deleted=tuple(deleted),
        purged=tuple(purge_titles),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--username", default="WikiSysop", help="Local wiki username")
    parser.add_argument("--password", default="DevWikiPassword-2026", help="Local wiki password")
    parser.add_argument(
        "--manifest-file",
        type=Path,
        help="Override managed state path for an isolated local wiki run",
    )
    parser.add_argument(
        "--include-clean-dependencies",
        action="store_true",
        help="Import development-only live-template dependencies into an isolated clean wiki",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print discovered pages without editing")
    args = parser.parse_args()

    pages = discover_pages(args.root, include_clean_dependencies=args.include_clean_dependencies)
    if args.dry_run:
        current = build_manifest(args.root, pages)
        for title, entry in current.items():
            print(f"{title}\t{entry.source_path}\t{entry.content_model}\t{entry.sha256}")
        print(f"Managed pages: {len(current)}")
        return

    endpoint = api_url(args.base_url)
    with httpx.Client(timeout=30.0) as client:
        login(client, endpoint, args.username, args.password)
        token = csrf_token(client, endpoint)
        report = reconcile_pages(
            client,
            endpoint,
            token,
            pages,
            args.root,
            manifest_file=args.manifest_file,
        )

    for action, titles in (
        ("Created", report.created),
        ("Updated", report.updated),
        ("Deleted", report.deleted),
        ("Purged", report.purged),
    ):
        for title in titles:
            print(f"{action} {title}")
    print(
        f"Managed pages: {len(pages)}. "
        f"Created {len(report.created)}, updated {len(report.updated)}, "
        f"unchanged {len(report.unchanged)}, deleted {len(report.deleted)}, "
        f"purged {len(report.purged)}."
    )


if __name__ == "__main__":
    main()
