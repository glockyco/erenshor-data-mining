#!/usr/bin/env python3
"""Run local MediaWiki render smoke tests for wiki Lua development."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple

import httpx


class SmokeResult(NamedTuple):
    """Result for one rendered-page expectation check."""

    title: str
    ok: bool
    missing: list[str]


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


def check_rendered_html(title: str, html: str, expected: list[str]) -> SmokeResult:
    """Check that all expected strings are present in rendered HTML."""
    missing = [needle for needle in expected if needle not in html]
    return SmokeResult(title=title, ok=not missing, missing=missing)


def parse_page(client: httpx.Client, endpoint: str, title: str) -> str:
    """Render a wiki page and return parsed HTML."""
    response = client.get(
        endpoint,
        params={
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Parse failed for {title}: {payload['error']}")
    return str(payload["parse"]["text"])


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument(
        "--expectations",
        type=Path,
        default=Path("wiki-dev/fixtures/smoke.tsv"),
        help="Tab-separated title/expected text file",
    )
    args = parser.parse_args()

    expectations = load_expectations(args.expectations)
    if not expectations:
        raise SystemExit(f"No smoke expectations found in {args.expectations}")

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

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
