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


class PageSource(NamedTuple):
    """A repository file and the MediaWiki page title it represents."""

    title: str
    path: Path


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


def discover_pages(root: Path) -> list[PageSource]:
    """Discover repo-owned module, template, and fixture article pages."""
    pages: list[PageSource] = []

    modules_dir = root / "wiki" / "modules"
    if modules_dir.exists():
        for path in sorted(modules_dir.rglob("*.lua")):
            relative = path.relative_to(modules_dir).with_suffix("")
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


def edit_page(client: httpx.Client, endpoint: str, token: str, page: PageSource, summary: str) -> None:
    """Upload one repo-owned page to MediaWiki."""
    response = client.post(
        endpoint,
        data={
            "action": "edit",
            "title": page.title,
            "text": page.path.read_text(encoding="utf-8"),
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
            print(f"Imported {page.title}")


if __name__ == "__main__":
    main()
