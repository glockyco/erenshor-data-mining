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
CARGO_SPELL_FIELDS = _cargo.CARGO_SPELL_FIELDS
CARGO_ABILITY_CLASS_QUERY_FIELDS = _cargo.CARGO_ABILITY_CLASS_QUERY_FIELDS
check_cargo_spell_rows = _cargo.check_cargo_spell_rows
check_cargo_ability_class_rows = _cargo.check_cargo_ability_class_rows
load_cargo_spell_expectations = _cargo.load_cargo_spell_expectations
load_cargo_ability_class_expectations = _cargo.load_cargo_ability_class_expectations
CARGO_SKILL_FIELDS = _cargo.CARGO_SKILL_FIELDS
check_cargo_skill_rows = _cargo.check_cargo_skill_rows
load_cargo_skill_expectations = _cargo.load_cargo_skill_expectations
CARGO_STANCE_FIELDS = _cargo.CARGO_STANCE_FIELDS
check_cargo_stance_rows = _cargo.check_cargo_stance_rows
load_cargo_stance_expectations = _cargo.load_cargo_stance_expectations
CARGO_DROP_QUERY_FIELDS = _cargo.CARGO_DROP_QUERY_FIELDS
check_cargo_drop_rows = _cargo.check_cargo_drop_rows
load_cargo_drop_expectations = _cargo.load_cargo_drop_expectations
CARGO_CONTAINER_DROP_QUERY_FIELDS = _cargo.CARGO_CONTAINER_DROP_QUERY_FIELDS
check_cargo_container_drop_rows = _cargo.check_cargo_container_drop_rows
load_cargo_container_drop_expectations = _cargo.load_cargo_container_drop_expectations
CARGO_OBTAINED_FROM_QUERY_FIELDS = _cargo.CARGO_OBTAINED_FROM_QUERY_FIELDS
check_cargo_obtained_from_rows = _cargo.check_cargo_obtained_from_rows
load_cargo_obtained_from_expectations = _cargo.load_cargo_obtained_from_expectations
CARGO_USED_IN_QUERY_FIELDS = _cargo.CARGO_USED_IN_QUERY_FIELDS
check_cargo_used_in_rows = _cargo.check_cargo_used_in_rows
load_cargo_used_in_expectations = _cargo.load_cargo_used_in_expectations
api_url = _mediawiki.api_url
query_cargo_table = _mediawiki.query_cargo_table

CARGO_TABLES = (
    "Items",
    "Characters",
    "Spells",
    "Skills",
    "Stances",
    "AbilityClasses",
    "Drops",
    "ContainerDrops",
    "ObtainedFrom",
    "UsedIn",
)
CARGO_TEMPLATES_BY_TABLE = {
    "Items": "Item",
    "Characters": "Character",
    "Spells": "Spell",
    "Skills": "Skill",
    "Stances": "Stance",
    "AbilityClasses": "AbilityClasses",
    "Drops": "Drops",
    "ContainerDrops": "ContainerDrops",
    "ObtainedFrom": "ItemObtainedFromStore",
    "UsedIn": "ItemUsedInStore",
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
    cargo_spells_path: Path,
    cargo_skills_path: Path,
    cargo_stances_path: Path,
    cargo_ability_classes_path: Path,
    cargo_drops_path: Path,
    cargo_container_drops_path: Path,
    cargo_obtained_from_path: Path,
    cargo_used_in_path: Path,
    cargo_absent_path: Path,
) -> list[str]:
    """Validate local Cargo rows against the smoke fixture expectations."""
    absent_pages = load_absent_pages(cargo_absent_path)
    failures: list[str] = []
    failures.extend(
        check_cargo_item_rows(
            rows=query_cargo_table(client, endpoint, "Items", CARGO_ITEM_FIELDS),
            expectations=load_cargo_item_expectations(cargo_items_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_character_rows(
            rows=query_cargo_table(client, endpoint, "Characters", CARGO_CHARACTER_FIELDS),
            expectations=load_cargo_character_expectations(cargo_characters_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_spell_rows(
            rows=query_cargo_table(client, endpoint, "Spells", CARGO_SPELL_FIELDS),
            expectations=load_cargo_spell_expectations(cargo_spells_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_skill_rows(
            rows=query_cargo_table(client, endpoint, "Skills", CARGO_SKILL_FIELDS),
            expectations=load_cargo_skill_expectations(cargo_skills_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_stance_rows(
            rows=query_cargo_table(client, endpoint, "Stances", CARGO_STANCE_FIELDS),
            expectations=load_cargo_stance_expectations(cargo_stances_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_ability_class_rows(
            rows=query_cargo_table(client, endpoint, "AbilityClasses", CARGO_ABILITY_CLASS_QUERY_FIELDS),
            expectations=load_cargo_ability_class_expectations(cargo_ability_classes_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_drop_rows(
            rows=query_cargo_table(client, endpoint, "Drops", CARGO_DROP_QUERY_FIELDS),
            expectations=load_cargo_drop_expectations(cargo_drops_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_container_drop_rows(
            rows=query_cargo_table(client, endpoint, "ContainerDrops", CARGO_CONTAINER_DROP_QUERY_FIELDS),
            expectations=load_cargo_container_drop_expectations(cargo_container_drops_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_obtained_from_rows(
            rows=query_cargo_table(client, endpoint, "ObtainedFrom", CARGO_OBTAINED_FROM_QUERY_FIELDS),
            expectations=load_cargo_obtained_from_expectations(cargo_obtained_from_path),
            absent_pages=absent_pages,
        )
    )
    failures.extend(
        check_cargo_used_in_rows(
            rows=query_cargo_table(client, endpoint, "UsedIn", CARGO_USED_IN_QUERY_FIELDS),
            expectations=load_cargo_used_in_expectations(cargo_used_in_path),
            absent_pages=absent_pages,
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
    parser.add_argument("--cargo-spells", type=Path, default=Path("wiki-dev/fixtures/cargo_spells.tsv"))
    parser.add_argument("--cargo-skills", type=Path, default=Path("wiki-dev/fixtures/cargo_skills.tsv"))
    parser.add_argument("--cargo-stances", type=Path, default=Path("wiki-dev/fixtures/cargo_stances.tsv"))
    parser.add_argument(
        "--cargo-ability-classes",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_ability_classes.tsv"),
    )
    parser.add_argument("--cargo-drops", type=Path, default=Path("wiki-dev/fixtures/cargo_drops.tsv"))
    parser.add_argument(
        "--cargo-container-drops",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_container_drops.tsv"),
    )
    parser.add_argument(
        "--cargo-obtained-from",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_obtained_from.tsv"),
    )
    parser.add_argument(
        "--cargo-used-in",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_used_in.tsv"),
    )
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
            cargo_spells_path=args.cargo_spells,
            cargo_skills_path=args.cargo_skills,
            cargo_stances_path=args.cargo_stances,
            cargo_ability_classes_path=args.cargo_ability_classes,
            cargo_drops_path=args.cargo_drops,
            cargo_container_drops_path=args.cargo_container_drops,
            cargo_absent_path=args.cargo_absent,
            cargo_used_in_path=args.cargo_used_in,
            cargo_obtained_from_path=args.cargo_obtained_from,
        )
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    print("PASS Cargo local validation")


if __name__ == "__main__":
    main()
