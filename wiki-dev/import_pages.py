#!/usr/bin/env python3
"""Import repository-owned wiki pages into a local MediaWiki instance.

This helper is intentionally small and explicit. It is for the local dev wiki,
not production deployment. Production interface pages use the dedicated guarded
interface-deploy path rather than this local importer.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple

import httpx

from erenshor.application.wiki_interface.gadgets import (
    GadgetSpec,
    gadget_source_pages,
    load_gadget_spec,
    reconcile_definition,
)

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
        PageSource(title=source.title, path=root / source.source_path) for source in gadget_source_pages(spec, root)
    ]


def discover_pages(root: Path) -> list[PageSource]:
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
            pages.append(PageSource(title=title, path=path))

    fixture_modules_dir = root / "wiki-dev" / "fixtures" / "modules"
    if fixture_modules_dir.exists():
        fixture_paths = sorted(
            fixture_modules_dir.rglob("*.lua"),
            key=lambda path: (len(path.relative_to(fixture_modules_dir).parts), path.as_posix()),
        )
        for path in fixture_paths:
            relative = path.relative_to(fixture_modules_dir).with_suffix("")
            title = "Module:" + "/".join(relative.parts)
            pages.append(PageSource(title=title, path=path))

    templates_dir = root / "wiki" / "templates"
    if templates_dir.exists():
        for path in sorted(templates_dir.rglob("*.wiki")):
            relative = path.relative_to(templates_dir).with_suffix("")
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
        pages.append(PageSource(title=title, path=path, content=content))
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


def edit_page(client: httpx.Client, endpoint: str, token: str, page: PageSource, summary: str) -> None:
    """Upload one local page to MediaWiki."""
    response = client.post(
        endpoint,
        data={
            "action": "edit",
            "title": page.title,
            "text": page_content(page),
            "summary": summary,
            "token": token,
            "format": "json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Edit failed for {page.title}: {payload['error']}")
    result = payload.get("edit", {}).get("result")
    if result != "Success":
        raise RuntimeError(f"Edit failed for {page.title}: {payload}")


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--username", default="WikiSysop", help="Local wiki username")
    parser.add_argument("--password", default="DevWikiPassword-2026", help="Local wiki password")
    parser.add_argument("--dry-run", action="store_true", help="Print discovered pages without editing")
    args = parser.parse_args()

    pages = discover_pages(args.root)
    if args.dry_run:
        for page in pages:
            print(f"{page.title}\t{page.path}")
        return

    endpoint = api_url(args.base_url)
    with httpx.Client(timeout=30.0) as client:
        login(client, endpoint, args.username, args.password)
        token = csrf_token(client, endpoint)
        for page in pages:
            edit_page(client, endpoint, token, page, "Import local dev wiki page")
            purge_page(client, endpoint, token, page.title)
            print(f"Imported {page.title}")


if __name__ == "__main__":
    main()
