"""Cloudflare-safe live-source capture for parity baselines.

The live wiki may challenge automated browsers. Capture therefore uses the
MediaWiki API to fetch live-rendered parser HTML, then renders that HTML with
live ResourceLoader stylesheets. This keeps routine baseline refreshes off live
browser routes while still comparing local output against live-rendered DOM and
live CSS.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

import httpx

if TYPE_CHECKING:
    from .compare import Snapshot
    from .contract import ParityPage, Target

USER_AGENT = "ErenshorDataBot/0.1 (local dev)"


def live_page_titles(pages: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Convert contract live paths into MediaWiki page titles for API parsing."""
    titles: list[tuple[str, str]] = []
    for name, live_path in pages:
        parsed = urlparse(live_path)
        path = parsed.path or live_path
        if path.startswith("/wiki/"):
            title = path.removeprefix("/wiki/")
        elif path.startswith("/index.php"):
            raise ValueError(f"Cannot derive live page title from index.php path: {live_path}")
        else:
            title = path.lstrip("/")
        titles.append((name, unquote(title).replace("_", " ")))
    return titles


def static_live_document(parsed_html: str, *, live_base: str) -> str:
    """Wrap live parser HTML in a live-styled static document."""
    root = live_base.rstrip("/")
    portable_infobox_styles = (
        f"{root}/load.php?lang=en&modules="
        "ext.PortableInfobox.styles%7Cskins.vector.styles.legacy"
        "&only=styles&skin=vector"
    )
    site_styles = f"{root}/load.php?lang=en&modules=site.styles&only=styles&skin=vector"
    return "\n".join(
        (
            "<!doctype html>",
            '<html class="client-js" lang="en" dir="ltr">',
            "<head>",
            '<meta charset="utf-8">',
            f'<link rel="stylesheet" href="{html.escape(portable_infobox_styles)}">',
            f'<link rel="stylesheet" href="{html.escape(site_styles)}">',
            "</head>",
            (
                '<body class="skin-vector-legacy mediawiki ltr sitedir-ltr '
                'mw-hide-empty-elt ns-0 ns-subject skin-vector action-view">'
            ),
            '<div id="content" class="mw-body" role="main">',
            '<div id="bodyContent" class="vector-body">',
            '<div id="mw-content-text">',
            parsed_html,
            "</div>",
            "</div>",
            "</div>",
            "</body>",
            "</html>",
        )
    )


def capture_live_source_snapshot(
    pages: Sequence[ParityPage],
    *,
    live_base: str,
    headless: bool = True,
) -> Snapshot:
    """Fetch live parser HTML through the API and extract styled snapshots locally."""
    from .extract import extract_html_snapshot

    endpoint = f"{live_base.rstrip('/')}/api.php"
    title_by_name = dict(live_page_titles([(page.name, page.live_path) for page in pages]))
    documents: list[tuple[str, str, Sequence[Target]]] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0) as client:
        for page in pages:
            parsed_html = fetch_parsed_html(client, endpoint, title_by_name[page.name])
            document = static_live_document(parsed_html, live_base=live_base)
            documents.append((page.name, document, page.targets))
    return extract_html_snapshot(documents, headless=headless)


def fetch_parsed_html(client: httpx.Client, endpoint: str, title: str) -> str:
    """Fetch live-rendered parser HTML for a page through MediaWiki's API."""
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
        raise RuntimeError(f"Live parse failed for {title}: {payload['error']}")
    return str(payload["parse"]["text"])
