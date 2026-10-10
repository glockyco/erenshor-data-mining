"""MediaWiki API helpers for local smoke tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """A rendered page's HTML and the categories it belongs to."""

    html: str
    categories: tuple[str, ...]


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


def parse_page(client: httpx.Client, endpoint: str, title: str) -> ParsedPage:
    """Render a wiki page and return its parsed HTML and category names."""
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
    categories = tuple(str(category["category"]) for category in parsed.get("categories", []))
    return ParsedPage(html=html, categories=categories)
