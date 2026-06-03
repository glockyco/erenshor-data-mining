"""Smoke-test orchestration for local MediaWiki validation."""

from __future__ import annotations

import httpx

from .cargo import (
    CARGO_CHARACTER_FIELDS,
    CARGO_ITEM_FIELDS,
    CargoExpectation,
    check_cargo_character_rows,
    check_cargo_item_rows,
)
from .mediawiki import parse_page, query_cargo_table
from .render import SmokeResult, check_rendered_html


def run_smoke_checks(
    endpoint: str,
    expectations: dict[str, list[str]],
    cargo_item_expectations: list[CargoExpectation],
    cargo_character_expectations: list[CargoExpectation],
    cargo_absent_pages: set[str],
) -> list[SmokeResult]:
    """Run rendered-page and Cargo checks against a local MediaWiki API endpoint."""
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
                rows=query_cargo_table(client, endpoint, "Items", CARGO_ITEM_FIELDS),
                expectations=cargo_item_expectations,
                absent_pages=cargo_absent_pages,
            )
            _record_cargo_result("Cargo Items", cargo_failures, failures)

        if cargo_character_expectations:
            cargo_failures = check_cargo_character_rows(
                rows=query_cargo_table(client, endpoint, "Characters", CARGO_CHARACTER_FIELDS),
                expectations=cargo_character_expectations,
            )
            _record_cargo_result("Cargo Characters", cargo_failures, failures)
    return failures


def _record_cargo_result(title: str, cargo_failures: list[str], failures: list[SmokeResult]) -> None:
    if cargo_failures:
        failures.append(SmokeResult(title=title, ok=False, missing=cargo_failures))
        print(f"FAIL {title}: missing {cargo_failures}")
    else:
        print(f"PASS {title}")
