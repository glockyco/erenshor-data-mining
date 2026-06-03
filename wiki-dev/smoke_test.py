#!/usr/bin/env python3
"""Run local MediaWiki render smoke tests for wiki Lua development."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import NamedTuple

import httpx


class SmokeResult(NamedTuple):
    """Result for one rendered-page expectation check."""

    title: str
    ok: bool
    missing: list[str]


class CargoExpectation(NamedTuple):
    """Expected row values in a local Cargo table."""

    page: str
    fields: dict[str, str]


CargoItemExpectation = CargoExpectation
CargoCharacterExpectation = CargoExpectation

CARGO_ITEM_FIELDS = (
    "Page",
    "StableKey",
    "Name",
    "Type",
    "Slot",
    "ItemLevel",
    "Damage",
    "Delay",
    "Armor",
    "BuyValue",
    "SellValue",
    "Image",
    "Classes",
    "Relic",
    "HasProc",
    "HasWornEffect",
)

CARGO_CHARACTER_FIELDS = (
    "Page",
    "StableKey",
    "Name",
    "Type",
    "Zones",
    "Level",
    "Class",
    "Faction",
    "SpawnChance",
    "HasDrops",
    "HasSpells",
    "MapSelector",
)


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


FORBIDDEN_HTML_MARKERS = (
    ("Lua error", "forbidden parser output: Lua error"),
    ("Script error", "forbidden parser output: Script error"),
    ('class="error"', "forbidden parser output: parser error"),
)

FORBIDDEN_HTML_PATTERNS = (
    (
        re.compile(r'<a\b(?=[^>]*\bclass="[^"]*\bnew\b)(?=[^>]*\btitle="Template:)', re.I),
        "forbidden parser output: unresolved template",
    ),
    (
        re.compile(r"<!--(?:(?!-->).)*\blimit exceeded\b(?:(?!-->).)*-->", re.I | re.S),
        "forbidden parser output: parser limit report",
    ),
)


def check_rendered_html(title: str, html: str, expected: list[str]) -> SmokeResult:
    """Check that expected strings are present and parser errors are absent."""
    missing = [needle for needle in expected if needle not in html]
    missing.extend(message for marker, message in FORBIDDEN_HTML_MARKERS if marker in html)
    missing.extend(message for pattern, message in FORBIDDEN_HTML_PATTERNS if pattern.search(html))
    return SmokeResult(title=title, ok=not missing, missing=missing)


def parse_page(client: httpx.Client, endpoint: str, title: str) -> str:
    """Render a wiki page and return parsed HTML."""
    response = client.get(
        endpoint,
        params={
            "action": "parse",
            "page": title,
            "prop": "text|categories",
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Parse failed for {title}: {payload['error']}")
    parsed = payload["parse"]
    html = str(parsed["text"])
    categories = "".join(f"\nCategory:{category['category']}" for category in parsed.get("categories", []))
    return html + categories


def load_expectations(path: Path) -> dict[str, list[str]]:
    """Load smoke expectations from a tab-separated file.

    Each non-comment line is: title<TAB>expected text. A title may appear
    multiple times to assert multiple expected strings.
    """
    expectations: dict[str, list[str]] = {}
    if not path.exists():
        return expectations
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        title, expected = line.split("\t", 1)
        expectations.setdefault(title, []).append(expected)
    return expectations


def load_cargo_expectations(path: Path, fields: tuple[str, ...]) -> list[CargoExpectation]:
    """Load expected Cargo rows from a tab-separated file."""
    if not path.exists():
        return []
    expectations: list[CargoExpectation] = []
    seen_rows: set[tuple[str, str]] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        values = line.split("\t")
        if len(values) != len(fields):
            raise ValueError(f"{path}: expected {len(fields)} tab-separated fields, got {len(values)}")
        row = dict(zip(fields, values, strict=True))
        page = row.pop("Page")
        stable_key = row["StableKey"]
        row_key = (page, stable_key)
        if row_key in seen_rows:
            raise ValueError(f"{path}: duplicate expected Cargo row {page} / {stable_key}")
        seen_rows.add(row_key)
        expectations.append(CargoExpectation(page=page, fields=row))
    return expectations


def load_cargo_item_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Items rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_ITEM_FIELDS)


def load_cargo_character_expectations(path: Path) -> list[CargoExpectation]:
    """Load expected Cargo Characters rows from a tab-separated file."""
    return load_cargo_expectations(path, CARGO_CHARACTER_FIELDS)


def load_absent_pages(path: Path) -> set[str]:
    """Load page names that must not have Cargo Items rows."""
    if not path.exists():
        return set()
    return {
        line
        for raw_line in path.read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    }


def query_cargo_table(
    client: httpx.Client,
    endpoint: str,
    table_name: str,
    fields: tuple[str, ...],
) -> list[dict[str, str]]:
    """Query a local Cargo table for smoke validation."""
    response = client.get(
        endpoint,
        params={
            "action": "cargoquery",
            "tables": table_name,
            "fields": ",".join(fields),
            "format": "json",
            "formatversion": "2",
            "limit": "500",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Cargo query failed: {payload['error']}")
    return [dict(row["title"]) for row in payload.get("cargoquery", [])]


def query_cargo_items(client: httpx.Client, endpoint: str) -> list[dict[str, str]]:
    """Query the local Cargo Items table for smoke validation."""
    return query_cargo_table(client, endpoint, "Items", CARGO_ITEM_FIELDS)


def query_cargo_characters(client: httpx.Client, endpoint: str) -> list[dict[str, str]]:
    """Query the local Cargo Characters table for smoke validation."""
    return query_cargo_table(client, endpoint, "Characters", CARGO_CHARACTER_FIELDS)


def check_cargo_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    table_label: str,
    absent_pages: set[str] | None = None,
) -> list[str]:
    rows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    rows_by_page: dict[str, list[dict[str, str]]] = {}
    duplicate_keys: set[tuple[str, str]] = set()
    for row in rows:
        page = row.get("Page", "")
        stable_key = row.get("StableKey", "")
        key = (page, stable_key)
        rows_by_page.setdefault(page, []).append(row)
        if key in rows_by_key:
            duplicate_keys.add(key)
            continue
        rows_by_key[key] = row
    failures: list[str] = []
    absent_pages = absent_pages or set()
    expected_keys = {(expected.page, expected.fields["StableKey"]) for expected in expectations}
    expected_pages = {expected.page for expected in expectations}
    for expected in expectations:
        key = (expected.page, expected.fields["StableKey"])
        row = rows_by_key.get(key)
        if row is None:
            failures.append(f"Cargo {table_label} missing row for {expected.page}")
            continue
        for field, expected_value in expected.fields.items():
            actual_value = row.get(field, "")
            if actual_value != expected_value:
                failures.append(
                    f"Cargo {table_label} row {expected.page} {field}: expected {expected_value}, got {actual_value}"
                )
    for page, stable_key in sorted(duplicate_keys):
        if page in expected_pages:
            failures.append(f"Cargo {table_label} duplicate row for {page} / {stable_key}")
    for page, stable_key in sorted(rows_by_key):
        if page in expected_pages and (page, stable_key) not in expected_keys:
            failures.append(f"Cargo {table_label} unexpected row for {page} / {stable_key}")
    for page in sorted(page for page in absent_pages if page in rows_by_page):
        failures.append(f"Cargo {table_label} unexpected row for {page}")
    return failures


def check_cargo_item_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
    absent_pages: set[str] | None = None,
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Items", absent_pages)


def check_cargo_character_rows(
    rows: list[dict[str, str]],
    expectations: list[CargoExpectation],
) -> list[str]:
    return check_cargo_rows(rows, expectations, "Characters")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument(
        "--expectations",
        type=Path,
        default=Path("wiki-dev/fixtures/smoke.tsv"),
        help="Tab-separated title/expected text file",
    )
    parser.add_argument(
        "--cargo-items",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_items.tsv"),
        help="Tab-separated Cargo Items smoke expectations",
    )
    parser.add_argument(
        "--cargo-absent",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_absent.tsv"),
        help="Page titles that must not have Cargo Items rows",
    )
    parser.add_argument(
        "--cargo-characters",
        type=Path,
        default=Path("wiki-dev/fixtures/cargo_characters.tsv"),
        help="Tab-separated Cargo Characters smoke expectations",
    )
    args = parser.parse_args()

    expectations = load_expectations(args.expectations)
    cargo_item_expectations = load_cargo_item_expectations(args.cargo_items)
    cargo_character_expectations = load_cargo_character_expectations(args.cargo_characters)
    cargo_absent_pages = load_absent_pages(args.cargo_absent)
    if not expectations and not cargo_item_expectations and not cargo_character_expectations:
        raise SystemExit(
            f"No smoke expectations found in {args.expectations}, {args.cargo_items}, or {args.cargo_characters}"
        )

    endpoint = api_url(args.base_url)
    failures: list[SmokeResult] = []
    with httpx.Client(timeout=30.0) as client:
        for title, expected in expectations.items():
            html = parse_page(client, endpoint, title)
            result = check_rendered_html(title=title, html=html, expected=expected)
            if result.ok:
                print(f"PASS {title}")
            else:
                failures.append(result)
                print(f"FAIL {title}: missing {result.missing}")

        if cargo_item_expectations:
            cargo_failures = check_cargo_item_rows(
                rows=query_cargo_items(client, endpoint),
                expectations=cargo_item_expectations,
                absent_pages=cargo_absent_pages,
            )
            if cargo_failures:
                failures.append(SmokeResult(title="Cargo Items", ok=False, missing=cargo_failures))
                print(f"FAIL Cargo Items: missing {cargo_failures}")
            else:
                print("PASS Cargo Items")

        if cargo_character_expectations:
            cargo_failures = check_cargo_character_rows(
                rows=query_cargo_characters(client, endpoint),
                expectations=cargo_character_expectations,
            )
            if cargo_failures:
                failures.append(SmokeResult(title="Cargo Characters", ok=False, missing=cargo_failures))
                print(f"FAIL Cargo Characters: missing {cargo_failures}")
            else:
                print("PASS Cargo Characters")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
