#!/usr/bin/env python3
"""Refresh and check local MediaWiki page renders.

Every checked page is null-edited and purged first, so no check reads output
that MediaWiki cached before a module or template changed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx
from smoke.mediawiki import api_url
from smoke.refresh import csrf_token, login, refresh_pages
from smoke.render import load_expectations
from smoke.runner import run_smoke_checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8088", help="Local wiki base URL")
    parser.add_argument("--username", default="WikiSysop", help="Local wiki username")
    parser.add_argument("--password", default="DevWikiPassword-2026", help="Local wiki password")
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
    with httpx.Client(timeout=30.0) as client:
        login(client, endpoint, args.username, args.password)
        refresh_pages(client, endpoint, csrf_token(client, endpoint), sorted(expectations))

    failures = run_smoke_checks(endpoint=endpoint, expectations=expectations)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
