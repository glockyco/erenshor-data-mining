"""Browser integration coverage for semantic item and ability tooltips."""

from __future__ import annotations

import os

import httpx
import pytest
from playwright.sync_api import Page, expect

WIKI_BASE_URL = os.environ.get("ERENSHOR_WIKI_BASE_URL", "http://localhost:8088")
API_URL = f"{WIKI_BASE_URL}/api.php"
FIXTURE_TITLE = "Semantic_Tooltip_Smoke"


def _tooltip_harness_ready() -> bool:
    try:
        response = httpx.get(
            API_URL,
            params={
                "action": "query",
                "titles": (
                    "MediaWiki:Gadget-item-tooltips.js|Semantic Tooltip Smoke|"
                    "Ability Tooltip Fixture|Unique Ability Tooltip Fixture"
                ),
                "format": "json",
                "formatversion": "2",
            },
            timeout=5.0,
        )
        _ = response.raise_for_status()
        pages = response.json()["query"]["pages"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return False
    return len(pages) == 4 and all("missing" not in page for page in pages)


@pytest.fixture
def wiki_page(browser_page: Page) -> Page:
    if not _tooltip_harness_ready():
        pytest.skip(
            "Current semantic-tooltip fixtures are not imported into the local wiki. "
            "Run 'uv run python wiki-dev/import_pages.py'."
        )

    browser_page.goto(
        f"{WIKI_BASE_URL}/index.php?title={FIXTURE_TITLE}",
        wait_until="domcontentloaded",
    )
    browser_page.locator("#erenshor-tooltip").wait_for(state="attached")
    return browser_page


def _overlay(page: Page):
    return page.locator("#erenshor-tooltip")


def test_tooltips_cover_keyed_unique_ambiguous_and_item_paths(wiki_page: Page) -> None:
    overlay = _overlay(wiki_page)

    wiki_page.locator(".erenshor-link--ability", has_text="Keyed exact ability").hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay).to_contain_text("Minor Lightning")
    expect(overlay.locator('[data-erenshor-key="spell:minor_lightning"]')).to_have_count(1)
    expect(overlay.locator('[data-erenshor-key="skill:backstab"]')).to_have_count(0)
    expect(overlay.locator('[data-erenshor-key="stance:aggressive"]')).to_have_count(0)
    expect(overlay.locator("a")).to_have_count(0)

    wiki_page.locator(".erenshor-link--ability", has_text="Keyed skill ability").hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay.locator('[data-erenshor-key="skill:backstab"]')).to_have_count(1)

    wiki_page.locator(".erenshor-link--ability", has_text="Keyed stance ability").hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay.locator('[data-erenshor-key="stance:aggressive"]')).to_have_count(1)

    unique_link = wiki_page.locator(".erenshor-link--ability", has_text="Unique positional ability")
    assert unique_link.get_attribute("data-erenshor-key") is None
    unique_link.hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay.locator('[data-erenshor-key="spell:minor_lightning"]')).to_have_count(1)

    wiki_page.locator(".erenshor-link--ability", has_text="Ambiguous positional ability").hover()
    expect(overlay).to_have_attribute("data-state", "error")
    expect(overlay).to_have_text("Preview unavailable.")

    wiki_page.locator(".erenshor-link--item", has_text="Abyssal Plate").hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay).to_contain_text("Abyssal Plate")
    expect(overlay).to_contain_text("Armor")
