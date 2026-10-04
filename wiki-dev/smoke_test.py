#!/usr/bin/env python3
"""Run local MediaWiki page-render smoke tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from smoke.mediawiki import api_url
from smoke.render import load_expectations
from smoke.runner import run_smoke_checks


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

    failures = run_smoke_checks(endpoint=api_url(args.base_url), expectations=expectations)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
