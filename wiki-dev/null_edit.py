#!/usr/bin/env python3
"""Null-edit local wiki fixture pages so Cargo rows and parser output refresh."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import httpx


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


def load_titles(*paths: Path) -> list[str]:
    """Load unique article titles from rendered and Cargo smoke fixtures."""
    titles: set[str] = set()
    for path in paths:
        titles.update(_load_first_column(path))
    return sorted(titles)


def _load_first_column(path: Path) -> set[str]:
    if not path.exists():
        return set()
    titles: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        title = line.split("\t", 1)[0].strip()
        if title:
            titles.add(title)
    return titles


def login(client: httpx.Client, endpoint: str, username: str, password: str) -> None:
    """Log in to MediaWiki using the classic token flow."""
    token_response = client.get(
        endpoint,
        params={"action": "query", "meta": "tokens", "type": "login", "format": "json"},
    )
    token_response.raise_for_status()
    token = str(token_response.json()["query"]["tokens"]["logintoken"])

    response = client.post(
        endpoint,
        data={
            "action": "login",
            "lgname": username,
            "lgpassword": password,
            "lgtoken": token,
            "format": "json",
        },
    )
    response.raise_for_status()
    result = response.json()["login"]["result"]
    if result != "Success":
        raise RuntimeError(f"MediaWiki login failed: {result}")


def csrf_token(client: httpx.Client, endpoint: str) -> str:
    """Fetch a CSRF token for edit operations."""
    response = client.get(
        endpoint,
        params={"action": "query", "meta": "tokens", "format": "json"},
    )
    response.raise_for_status()
    return str(response.json()["query"]["tokens"]["csrftoken"])


def page_source(client: httpx.Client, endpoint: str, title: str) -> tuple[str, str]:
    """Return current page wikitext and timestamp for a null edit."""
    response = client.get(
        endpoint,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "content|timestamp",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Fetch failed for {title}: {payload['error']}")
    page = payload["query"]["pages"][0]
    if page.get("missing"):
        raise RuntimeError(f"Cannot null-edit missing page: {title}")
    revision = page["revisions"][0]
    content = str(revision["slots"]["main"]["content"])
    timestamp = str(revision["timestamp"])
    return content, timestamp


def null_edit_page(client: httpx.Client, endpoint: str, token: str, title: str) -> None:
    """Submit the current page source unchanged to refresh parser/Cargo state."""
    content, timestamp = page_source(client, endpoint, title)
    response = client.post(
        endpoint,
        data={
            "action": "edit",
            "title": title,
            "text": content,
            "token": token,
            "basetimestamp": timestamp,
            "summary": "Local validation null edit",
            "bot": "1",
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if "error" in payload:
        raise RuntimeError(f"Null edit failed for {title}: {payload['error']}")
    result = payload.get("edit", {}).get("result")
    if result != "Success":
        raise RuntimeError(f"Null edit failed for {title}: {payload}")


def purge_page(client: httpx.Client, endpoint: str, token: str, title: str) -> None:
    """Purge one page after the whole fixture set has refreshed."""
    response = client.post(
        endpoint,
        data={
            "action": "purge",
            "titles": title,
            "token": token,
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if "error" in payload:
        raise RuntimeError(f"Purge failed for {title}: {payload['error']}")


def refresh_pages(client: httpx.Client, endpoint: str, token: str, titles: list[str]) -> None:
    """Null-edit every page, then purge every page after dependent data is stable."""
    for title in titles:
        null_edit_page(client, endpoint, token, title)
        print(f"Null-edited {title}")
    for title in titles:
        purge_page(client, endpoint, token, title)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument("--username", default="WikiSysop", help="Local wiki username")
    parser.add_argument("--password", default="DevWikiPassword-2026", help="Local wiki password")
    parser.add_argument("--smoke", type=Path, default=Path("wiki-dev/fixtures/smoke.tsv"))
    parser.add_argument("--cargo-items", type=Path, default=Path("wiki-dev/fixtures/cargo_items.tsv"))
    parser.add_argument("--cargo-characters", type=Path, default=Path("wiki-dev/fixtures/cargo_characters.tsv"))
    parser.add_argument("--cargo-spells", type=Path, default=Path("wiki-dev/fixtures/cargo_spells.tsv"))
    parser.add_argument(
        "--cargo-ability-classes",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_ability_classes.tsv"),
    )
    args = parser.parse_args()

    titles = load_titles(
        args.smoke,
        args.cargo_items,
        args.cargo_characters,
        args.cargo_spells,
        args.cargo_ability_classes,
    )
    endpoint = api_url(args.base_url)
    with httpx.Client(timeout=30.0) as client:
        login(client, endpoint, args.username, args.password)
        token = csrf_token(client, endpoint)
        refresh_pages(client, endpoint, token, titles)


if __name__ == "__main__":
    main()
