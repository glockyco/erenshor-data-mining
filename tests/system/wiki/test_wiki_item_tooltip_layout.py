"""Browser coverage for the layout of item tooltip cards on the local wiki."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

WIKI_BASE_URL = os.environ.get("ERENSHOR_WIKI_BASE_URL", "http://localhost:8088")

# The game centers the effect lines below the description, like the description itself.
_TEXT_OFFSETS_FROM_CARD_CENTER = """
selectors => selectors.flatMap(selector =>
    [...document.querySelectorAll(selector)].map(line => {
        const card = line.closest('.item-tooltip');
        const range = document.createRange();
        range.selectNodeContents(line);
        const text = range.getBoundingClientRect();
        const box = card.getBoundingClientRect();
        return {
            selector,
            text: line.textContent.trim(),
            offset: (text.left + text.right) / 2 - (box.left + box.right) / 2,
        };
    })
)
"""


@pytest.mark.parametrize(
    ("title", "selectors"),
    [
        (
            "Item_Effect_Lines_Fixture",
            [".item-tooltip-activatable-name", ".item-tooltip .item-spell-flag"],
        ),
        ("Abyssal_Plate", [".item-tooltip-worn-name", ".item-tooltip-proc-usage"]),
    ],
)
def test_effect_lines_are_centered_in_the_card(browser_page: Page, title: str, selectors: list[str]) -> None:
    browser_page.goto(f"{WIKI_BASE_URL}/index.php?title={title}", wait_until="domcontentloaded")
    browser_page.locator(".item-tooltip").first.wait_for()

    lines = browser_page.evaluate(_TEXT_OFFSETS_FROM_CARD_CENTER, selectors)

    assert {line["selector"] for line in lines} == set(selectors)
    assert [line for line in lines if abs(line["offset"]) > 2] == []


def test_historical_notice_does_not_push_item_tooltip_below_infobox(browser_page: Page) -> None:
    browser_page.goto(f"{WIKI_BASE_URL}/index.php?title=Historical_Layout_Item", wait_until="domcontentloaded")
    notice = browser_page.locator(".navbox").first
    infobox = browser_page.locator(".portable-infobox").first
    tooltip = browser_page.locator(".item-tooltip").first
    tooltip.wait_for()

    notice_box = notice.bounding_box()
    infobox_box = infobox.bounding_box()
    tooltip_box = tooltip.bounding_box()

    assert notice_box is not None and infobox_box is not None and tooltip_box is not None
    assert notice_box["y"] + notice_box["height"] <= infobox_box["y"]
    assert tooltip_box["y"] < infobox_box["y"] + infobox_box["height"]
    assert tooltip_box["x"] + tooltip_box["width"] <= infobox_box["x"]
