"""Refresh the local wiki pages that the smoke test checks.

An imported module or template change reaches a page that uses it only when
the job queue re-renders the page, so a check could read output cached before
the change. A null edit of every checked page, followed by a purge once all of
them are refreshed, gives each check the current render.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


def login(client: httpx.Client, endpoint: str, username: str, password: str) -> None:
    """Log in to MediaWiki using the classic token flow."""
    token_response = client.get(
        endpoint,
        params={"action": "query", "meta": "tokens", "type": "login", "format": "json"},
    )
    token_response.raise_for_status()
    token = str(token_response.json()["query"]["tokens"]["logintoken"])

    response = client.post(
        endpoint,
        data={
            "action": "login",
            "lgname": username,
            "lgpassword": password,
            "lgtoken": token,
            "format": "json",
        },
    )
    response.raise_for_status()
    result = response.json()["login"]["result"]
    if result != "Success":
        raise RuntimeError(f"MediaWiki login failed: {result}")


def csrf_token(client: httpx.Client, endpoint: str) -> str:
    """Fetch a CSRF token for edit operations."""
    response = client.get(
        endpoint,
        params={"action": "query", "meta": "tokens", "format": "json"},
    )
    response.raise_for_status()
    return str(response.json()["query"]["tokens"]["csrftoken"])


def page_source(client: httpx.Client, endpoint: str, title: str) -> tuple[str, str]:
    """Return current page wikitext and timestamp for a null edit."""
    response = client.get(
        endpoint,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "content|timestamp",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Fetch failed for {title}: {payload['error']}")
    page = payload["query"]["pages"][0]
    if page.get("missing"):
        raise RuntimeError(f"Cannot null-edit missing page: {title}")
    revision = page["revisions"][0]
    content = str(revision["slots"]["main"]["content"])
    timestamp = str(revision["timestamp"])
    return content, timestamp


def null_edit_page(client: httpx.Client, endpoint: str, token: str, title: str) -> None:
    """Submit the current page source unchanged to refresh parser state."""
    content, timestamp = page_source(client, endpoint, title)
    response = client.post(
        endpoint,
        data={
            "action": "edit",
            "title": title,
            "text": content,
            "token": token,
            "basetimestamp": timestamp,
            "summary": "Local validation null edit",
            "bot": "1",
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if "error" in payload:
        raise RuntimeError(f"Null edit failed for {title}: {payload['error']}")
    result = payload.get("edit", {}).get("result")
    if result != "Success":
        raise RuntimeError(f"Null edit failed for {title}: {payload}")


def purge_page(client: httpx.Client, endpoint: str, token: str, title: str) -> None:
    """Purge one page after the whole fixture set has refreshed."""
    response = client.post(
        endpoint,
        data={
            "action": "purge",
            "titles": title,
            "token": token,
            "format": "json",
            "formatversion": "2",
        },
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    if "error" in payload:
        raise RuntimeError(f"Purge failed for {title}: {payload['error']}")


def refresh_pages(client: httpx.Client, endpoint: str, token: str, titles: list[str]) -> None:
    """Null-edit every page, then purge every page after dependent data is stable."""
    for title in titles:
        null_edit_page(client, endpoint, token, title)
    for title in titles:
        purge_page(client, endpoint, token, title)
