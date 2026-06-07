#!/usr/bin/env python3
"""Recreate and validate local Cargo tables for Lua/Cargo cutover checks."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx


def _load_helper(relative_path: str) -> ModuleType:
    path = Path(__file__).resolve().parent / relative_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_cargo = _load_helper("smoke/cargo.py")
_mediawiki = _load_helper("smoke/mediawiki.py")

CARGO_CHARACTER_FIELDS = _cargo.CARGO_CHARACTER_FIELDS
CARGO_ITEM_FIELDS = _cargo.CARGO_ITEM_FIELDS
check_cargo_character_rows = _cargo.check_cargo_character_rows
check_cargo_item_rows = _cargo.check_cargo_item_rows
load_absent_pages = _cargo.load_absent_pages
load_cargo_character_expectations = _cargo.load_cargo_character_expectations
load_cargo_item_expectations = _cargo.load_cargo_item_expectations
api_url = _mediawiki.api_url
query_cargo_table = _mediawiki.query_cargo_table

CARGO_TABLES = ("Items", "Characters")
CARGO_TEMPLATES_BY_TABLE = {
    "Items": "Item",
    "Characters": "Character",
}


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
    """Fetch a CSRF token for Cargo recreation operations."""
    response = client.get(endpoint, params={"action": "query", "meta": "tokens", "format": "json"})
    response.raise_for_status()
    return str(response.json()["query"]["tokens"]["csrftoken"])


def recreate_cargo_tables(client: httpx.Client, endpoint: str, token: str) -> None:
    """Recreate the local Cargo tables declared by repo-owned templates."""
    for template in CARGO_TEMPLATES_BY_TABLE.values():
        response = client.post(
            endpoint,
            data={
                "action": "cargorecreatetables",
                "template": template,
                "token": token,
                "format": "json",
                "formatversion": "2",
            },
        )
        response.raise_for_status()
        _raise_on_api_error(response.json(), f"recreate Cargo tables for Template:{template}")


def _raise_on_api_error(payload: dict[str, Any], action: str) -> None:
    if "error" in payload:
        raise RuntimeError(f"Could not {action}: {payload['error']}")


def validate_cargo_rows(
    *,
    client: httpx.Client,
    endpoint: str,
    cargo_items_path: Path,
    cargo_characters_path: Path,
    cargo_absent_path: Path,
) -> list[str]:
    """Validate local Cargo rows against the smoke fixture expectations."""
    failures: list[str] = []
    failures.extend(
        check_cargo_item_rows(
            rows=query_cargo_table(client, endpoint, "Items", CARGO_ITEM_FIELDS),
            expectations=load_cargo_item_expectations(cargo_items_path),
            absent_pages=load_absent_pages(cargo_absent_path),
        )
    )
    failures.extend(
        check_cargo_character_rows(
            rows=query_cargo_table(client, endpoint, "Characters", CARGO_CHARACTER_FIELDS),
            expectations=load_cargo_character_expectations(cargo_characters_path),
            absent_pages=load_absent_pages(cargo_absent_path),
        )
    )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument("--username", default="WikiSysop", help="Local wiki username")
    parser.add_argument("--password", default="DevWikiPassword-2026", help="Local wiki password")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate local Cargo table definitions, then exit before row validation",
    )
    parser.add_argument("--cargo-items", type=Path, default=Path("wiki-dev/fixtures/cargo_items.tsv"))
    parser.add_argument("--cargo-characters", type=Path, default=Path("wiki-dev/fixtures/cargo_characters.tsv"))
    parser.add_argument("--cargo-absent", type=Path, default=Path("wiki-dev/fixtures/cargo_absent.tsv"))
    args = parser.parse_args()

    endpoint = api_url(args.base_url)
    with httpx.Client(timeout=60.0) as client:
        if args.recreate:
            login(client, endpoint, args.username, args.password)
            token = csrf_token(client, endpoint)
            recreate_cargo_tables(client, endpoint, token)
            print("Recreated Cargo tables: " + ", ".join(CARGO_TABLES))
            print("Run `uv run python wiki-dev/null_edit.py` before validating rows.")
            return

        failures = validate_cargo_rows(
            client=client,
            endpoint=endpoint,
            cargo_items_path=args.cargo_items,
            cargo_characters_path=args.cargo_characters,
            cargo_absent_path=args.cargo_absent,
        )
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    print("PASS Cargo local validation")


if __name__ == "__main__":
    main()
