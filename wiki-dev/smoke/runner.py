"""Smoke-test orchestration for local MediaWiki validation."""

from __future__ import annotations

import httpx

from .mediawiki import parse_page
from .render import SmokeResult, check_rendered_html


def run_smoke_checks(endpoint: str, expectations: dict[str, list[str]]) -> list[SmokeResult]:
    """Check rendered pages against a local MediaWiki API endpoint."""
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
    return failures
