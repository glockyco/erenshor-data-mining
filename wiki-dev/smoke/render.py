"""Rendered-page smoke expectations for the local MediaWiki harness."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple


class SmokeResult(NamedTuple):
    """Result for one rendered-page expectation check."""

    title: str
    ok: bool
    missing: list[str]


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


def load_expectations(path: Path) -> dict[str, list[str]]:
    """Load rendered-page smoke expectations from a tab-separated file.

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
