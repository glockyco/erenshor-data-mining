"""Browser integration coverage for semantic item and ability tooltips."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

pytestmark = pytest.mark.integration

WIKI_BASE_URL = "http://localhost:8088"
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
def wiki_page() -> Iterator[Page]:
    if not _tooltip_harness_ready():
        pytest.skip(
            "Current semantic-tooltip fixtures are not imported into the local wiki. "
            "Run 'uv run python wiki-dev/import_pages.py'."
        )

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as error:
            pytest.skip(f"Playwright Chromium is unavailable: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            _ = page.goto(
                f"{WIKI_BASE_URL}/index.php?title={FIXTURE_TITLE}",
                wait_until="domcontentloaded",
            )
            page.locator("#erenshor-tooltip").wait_for(state="attached")
            yield page
        finally:
            browser.close()
        assert page_errors == []


def _overlay(page: Page):
    return page.locator("#erenshor-tooltip")


def test_keyed_and_unique_ability_links_load_the_correct_card(wiki_page: Page) -> None:
    overlay = _overlay(wiki_page)

    wiki_page.locator(".erenshor-link--ability", has_text="Keyed exact ability").hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay).to_contain_text("Minor Lightning")
    expect(overlay.locator('[data-erenshor-key="spell:minor_lightning"]')).to_have_count(1)
    expect(overlay.locator('[data-erenshor-key="skill:backstab"]')).to_have_count(0)
    expect(overlay.locator("a")).to_have_count(0)

    unique_link = wiki_page.locator(".erenshor-link--ability", has_text="Unique positional ability")
    assert unique_link.get_attribute("data-erenshor-key") is None
    unique_link.hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay.locator('[data-erenshor-key="spell:minor_lightning"]')).to_have_count(1)


def test_ambiguous_ability_is_unavailable_and_items_still_load(wiki_page: Page) -> None:
    overlay = _overlay(wiki_page)

    wiki_page.locator(".erenshor-link--ability", has_text="Ambiguous positional ability").hover()
    expect(overlay).to_have_attribute("data-state", "error")
    expect(overlay).to_have_text("Preview unavailable.")

    wiki_page.locator(".erenshor-link--item", has_text="Abyssal Plate").hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay).to_contain_text("Abyssal Plate")
    expect(overlay).to_contain_text("Armor")
