#!/usr/bin/env python3
"""Import repository-owned wiki pages into a local MediaWiki instance.

This helper is intentionally small and explicit. It is for the local dev wiki,
not production deployment. Production deploys should use the project CLI with
basetimestamp/revision protection once that path exists.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple

import httpx

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

# Registration line for the repo-owned presentation gadget. A CSS-only
# `hidden|default` gadget loads for everyone and cannot be disabled, the
# documented modular alternative to MediaWiki:Common.css. The live cutover adds
# the same line to the production Gadgets-definition.
GADGET_DEFINITION_LINE = "* erenshor[ResourceLoader|default|hidden|type=styles]|erenshor.css"


class PageSource(NamedTuple):
    """A local file and the MediaWiki page title it represents."""

    title: str
    path: Path
    content: str | None = None


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


def discover_pages(root: Path) -> list[PageSource]:
    """Discover interface, module, template, and fixture article pages."""
    pages: list[PageSource] = []

    pages.extend(discover_interface_pages(root))

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

    gadgets_dir = root / "wiki" / "gadgets"
    if gadgets_dir.exists():
        for path in sorted(gadgets_dir.rglob("*.css")):
            title = "MediaWiki:Gadget-" + path.name
            pages.append(PageSource(title=title, path=path))

    fixture_pages_dir = root / "wiki-dev" / "fixtures" / "pages"
    if fixture_pages_dir.exists():
        for path in sorted(fixture_pages_dir.rglob("*.wiki")):
            relative = path.relative_to(fixture_pages_dir).with_suffix("")
            title = "/".join(relative.parts).replace("_", " ")
            pages.append(PageSource(title=title, path=path))

    return pages


def discover_interface_pages(root: Path) -> list[PageSource]:
    """Discover synced live MediaWiki interface pages for local preview."""
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

    pages: list[PageSource] = []
    for path in sorted(interface_dir.iterdir()):
        if not path.is_file():
            continue
        title = "MediaWiki:" + path.name.replace("__", "/")
        content = None
        if path.name == "Common.css" and theme_css:
            content = theme_css + "\n" + path.read_text(encoding="utf-8")
        if path.name == "Common.js" and theme_js:
            content = theme_js + "\n" + path.read_text(encoding="utf-8")
        if path.name == "Gadgets-definition":
            content = path.read_text(encoding="utf-8").rstrip() + "\n" + GADGET_DEFINITION_LINE + "\n"
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
