"""MediaWiki API helpers for local smoke tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx


def api_url(base_url: str) -> str:
    """Return the MediaWiki API endpoint for a wiki base URL."""
    return f"{base_url.rstrip('/')}/api.php"


def parse_page(client: httpx.Client, endpoint: str, title: str) -> str:
    """Render a wiki page and return parsed HTML plus category markers."""
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
