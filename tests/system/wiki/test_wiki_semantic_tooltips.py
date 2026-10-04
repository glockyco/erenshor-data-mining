"""Browser integration coverage for semantic item and ability tooltips."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

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
                    "Ability Tooltip Fixture|Unique Ability Tooltip Fixture|"
                    "Tooltip Placement Fixture"
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
    return len(pages) == 5 and all("missing" not in page for page in pages)


def _assert_repository_gadgets_loaded() -> None:
    response = httpx.get(
        API_URL,
        params={
            "action": "query",
            "prop": "revisions",
            "titles": "MediaWiki:Gadget-item-tooltips.js|MediaWiki:Gadget-erenshor.css",
            "rvslots": "main",
            "rvprop": "content",
            "format": "json",
            "formatversion": "2",
        },
        timeout=5.0,
    )
    response.raise_for_status()
    pages = response.json()["query"]["pages"]
    sources = {
        "MediaWiki:Gadget-item-tooltips.js": "item-tooltips.js",
        "MediaWiki:Gadget-erenshor.css": "erenshor.css",
    }
    root = Path(__file__).resolve().parents[3]
    for page in pages:
        expected = (root / "wiki" / "gadgets" / sources[page["title"]]).read_text(encoding="utf-8")
        actual = page["revisions"][0]["slots"]["main"]["content"]
        assert actual.rstrip() == expected.rstrip(), (
            f"{page['title']} is stale. Run 'uv run python wiki-dev/import_pages.py'."
        )


@pytest.fixture
def placement_page(browser_page: Page) -> Page:
    if not _tooltip_harness_ready():
        pytest.skip("Import the tooltip fixtures with 'uv run python wiki-dev/import_pages.py'.")
    _assert_repository_gadgets_loaded()
    browser_page.goto(
        f"{WIKI_BASE_URL}/index.php?title=Tooltip_Placement_Fixture",
        wait_until="domcontentloaded",
    )
    browser_page.locator("#erenshor-tooltip").wait_for(state="attached")
    return browser_page


@pytest.fixture
def wiki_page(browser_page: Page) -> Page:
    if not _tooltip_harness_ready():
        pytest.skip(
            "Current semantic-tooltip fixtures are not imported into the local wiki. "
            "Run 'uv run python wiki-dev/import_pages.py'."
        )

    _assert_repository_gadgets_loaded()
    browser_page.goto(
        f"{WIKI_BASE_URL}/index.php?title={FIXTURE_TITLE}",
        wait_until="domcontentloaded",
    )
    browser_page.locator("#erenshor-tooltip").wait_for(state="attached")
    return browser_page


def _overlay(page: Page):
    return page.locator("#erenshor-tooltip")


def _box(locator: Locator) -> dict[str, float]:
    box = locator.bounding_box()
    assert box is not None
    return box


def _inside_viewport(page: Page, box: dict[str, float]) -> None:
    viewport = page.viewport_size
    assert viewport is not None
    assert box["x"] >= 0
    assert box["y"] >= 0
    assert box["x"] + box["width"] <= viewport["width"]
    assert box["y"] + box["height"] <= viewport["height"]


def test_table_tooltip_opens_beside_link_without_covering_next_row(placement_page: Page) -> None:
    link = placement_page.locator("table .erenshor-link--item")
    row = placement_page.locator("table tr").nth(1)
    overlay = _overlay(placement_page)
    link.hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay).to_have_attribute("data-placement", "right")
    trigger_box = _box(link)
    overlay_box = _box(overlay)
    row_box = _box(row)
    assert overlay_box["x"] >= trigger_box["x"] + trigger_box["width"] + 1
    assert overlay_box["x"] >= row_box["x"] + row_box["width"]
    _inside_viewport(placement_page, overlay_box)


def test_right_edge_tooltip_opens_left_of_link(placement_page: Page) -> None:
    link = placement_page.locator(".erenshor-link--item", has_text="Right edge item")
    overlay = _overlay(placement_page)
    link.hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay).to_have_attribute("data-placement", "left")
    trigger_box = _box(link)
    overlay_box = _box(overlay)
    assert overlay_box["x"] + overlay_box["width"] <= trigger_box["x"] - 1
    _inside_viewport(placement_page, overlay_box)


def test_tall_tooltip_stays_in_viewport_and_scrolls(placement_page: Page) -> None:
    placement_page.set_viewport_size({"width": 1440, "height": 320})
    link = placement_page.locator("table .erenshor-link--item")
    overlay = _overlay(placement_page)
    link.hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    expect(overlay).to_have_attribute("data-placement", "right")
    _inside_viewport(placement_page, _box(overlay))
    heights = overlay.evaluate("(element) => [element.scrollHeight, element.clientHeight]")
    assert heights[0] > heights[1]
    assert overlay.evaluate("(element) => { element.scrollTop = 100; return element.scrollTop; }") > 0


def test_tooltip_falls_back_below_or_above_when_neither_side_fits(placement_page: Page) -> None:
    placement_page.set_viewport_size({"width": 320, "height": 640})
    link = placement_page.locator("table .erenshor-link--item")
    overlay = _overlay(placement_page)
    link.hover()
    expect(overlay).to_have_attribute("data-state", "ready")
    assert overlay.get_attribute("data-placement") in {"above", "below"}
    trigger_box = _box(link)
    overlay_box = _box(overlay)
    if overlay.get_attribute("data-placement") == "below":
        assert overlay_box["y"] >= trigger_box["y"] + trigger_box["height"]
    else:
        assert overlay_box["y"] + overlay_box["height"] <= trigger_box["y"]
    _inside_viewport(placement_page, overlay_box)


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
