"""Cargo row smoke expectations for the local MediaWiki harness."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


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
    """Load page names that must not have Cargo rows."""
    if not path.exists():
        return set()
    return {
        line
        for raw_line in path.read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    }


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
