"""Browser integration coverage for the MediaWiki semantic-link picker."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from html import unescape

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

WIKI_BASE_URL = os.environ.get("ERENSHOR_WIKI_BASE_URL", "http://localhost:8088")
API_URL = f"{WIKI_BASE_URL}/api.php"
SOURCE_TITLE = "Smoke_Page"
VE_TITLE = "Lua_AbilityLink_Smoke"


def _picker_harness_ready() -> bool:
    try:
        response = httpx.get(
            API_URL,
            params={
                "action": "query",
                "titles": (
                    "MediaWiki:Gadget-semantic-link-picker-core.js|"
                    "MediaWiki:Gadget-semantic-link-picker.js|Lua AbilityLink Smoke"
                ),
                "format": "json",
                "formatversion": "2",
            },
            timeout=5.0,
        )
        response.raise_for_status()
        pages = response.json()["query"]["pages"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return False
    return len(pages) == 3 and all("missing" not in page for page in pages)


@pytest.fixture
def wiki_page(browser_page: Page) -> Page:
    if not _picker_harness_ready():
        pytest.skip(
            "Current semantic-picker fixtures are not imported into the local wiki. "
            "Run 'uv run python wiki-dev/import_pages.py'."
        )
    return browser_page


def _open_source_editor(page: Page) -> None:
    page.goto(
        f"{WIKI_BASE_URL}/index.php?title={SOURCE_TITLE}&action=edit",
        wait_until="domcontentloaded",
    )
    start = page.get_by_role("button", name="Start editing", exact=True)
    textarea = page.locator("#wpTextbox1")
    toolbar_tool = page.locator(".wikiEditor-ui-toolbar .tool[rel=erenshorLink]")
    textarea.wait_for()
    start.or_(toolbar_tool).first.wait_for()
    if start.is_visible():
        start.click()
    else:
        welcome = page.locator(".ve-init-mw-welcomeDialog.oo-ui-window-active")
        with suppress(PlaywrightTimeoutError):
            welcome.wait_for(state="visible", timeout=2_000)
        if welcome.is_visible():
            welcome.get_by_role("button", name="Start editing", exact=True).click()
    toolbar_tool.wait_for()


def _set_source_selection(page: Page, text: str, start: int, end: int) -> None:
    page.locator("#wpTextbox1").evaluate(
        """(textarea, selection) => {
            textarea.value = selection.text;
            textarea.focus();
            textarea.setSelectionRange(selection.start, selection.end);
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        {"text": text, "start": start, "end": end},
    )


def _open_source_picker(page: Page) -> None:
    page.locator(".wikiEditor-ui-toolbar .tool[rel=erenshorLink]").click()


def _active_dialog(page: Page) -> Locator:
    return page.locator(".semantic-link-picker-dialog.oo-ui-window-active")


def _open_visual_editor(page: Page) -> None:
    page.goto(
        f"{WIKI_BASE_URL}/index.php?title={VE_TITLE}&veaction=edit",
        wait_until="domcontentloaded",
    )
    surface = page.locator(".ve-ui-surface")
    surface.wait_for()
    start = page.get_by_role("button", name="Start editing", exact=True)
    insert = page.get_by_role("button", name="Insert", exact=True)
    start.or_(insert).first.wait_for()
    if start.is_visible():
        start.click()
    insert.wait_for()


def _open_visual_picker(page: Page) -> None:
    page.get_by_role("button", name="Insert", exact=True).click()
    page.get_by_role("button", name="More", exact=True).click()
    page.get_by_role("button", name="Erenshor link", exact=True).click()


def _visual_template_params(page: Page, stable_key: str) -> list[dict[str, str]]:
    payloads = page.locator('[typeof~="mw:Transclusion"][data-mw]').evaluate_all(
        """elements => elements.map(element => element.getAttribute('data-mw'))"""
    )
    matches: list[dict[str, str]] = []
    for payload in payloads:
        if payload is None:
            continue
        data = json.loads(payload)
        for part in data.get("parts", []):
            template = part.get("template")
            if not isinstance(template, dict):
                continue
            params = template.get("params", {})
            if params.get("stablekey", {}).get("wt") == stable_key:
                matches.append({name: value.get("wt", "") for name, value in params.items()})
    return matches


def _wait_for_visual_key(page: Page, stable_key: str) -> None:
    page.wait_for_function(
        """stableKey => Array.from(
            document.querySelectorAll('[typeof~="mw:Transclusion"][data-mw]')
        ).some(element => {
            const data = JSON.parse(element.getAttribute('data-mw'));
            return (data.parts || []).some(part =>
                part.template && part.template.params &&
                part.template.params.stablekey &&
                part.template.params.stablekey.wt === stableKey
            );
        })""",
        arg=stable_key,
    )


def _render_wikitext(wikitext: str) -> str:
    response = httpx.get(
        API_URL,
        params={
            "action": "parse",
            "text": wikitext,
            "prop": "text",
            "format": "json",
            "formatversion": "2",
        },
        timeout=10.0,
    )
    response.raise_for_status()
    return unescape(response.json()["parse"]["text"])


def test_source_picker_inserts_exact_duplicate_and_escapes_label(wiki_page: Page) -> None:
    _open_source_editor(wiki_page)
    selected_text = "Flame Bolt"
    _set_source_selection(wiki_page, selected_text, 0, len(selected_text))
    _open_source_picker(wiki_page)

    dialog = _active_dialog(wiki_page)
    expect(dialog).to_be_visible()
    search = dialog.get_by_role("combobox", name="Search")
    options = dialog.get_by_role("option")
    expect(search).to_have_value(selected_text)
    expect(search).to_have_attribute("aria-expanded", "true")
    expect(options).to_have_count(2)
    assert options.nth(0).get_attribute("data-erenshor-key") == "spell:flame_bolt"
    assert options.nth(1).get_attribute("data-erenshor-key") == "spell:flame_bolt_greater"
    assert all(options.nth(index).get_attribute("aria-selected") == "false" for index in range(2))

    search.press("ArrowDown")
    search.press("ArrowDown")
    search.press("Enter")
    assert options.nth(1).get_attribute("aria-selected") == "true"
    assert dialog.get_by_role("textbox", name="Link text").input_value() == selected_text
    dialog.get_by_role("button", name="Insert", exact=True).click()
    dialog.wait_for(state="hidden")

    assert wiki_page.locator("#wpTextbox1").input_value() == ("{{AbilityLink|stablekey=spell:flame_bolt_greater}}")

    _set_source_selection(wiki_page, selected_text, 0, len(selected_text))
    _open_source_picker(wiki_page)
    dialog = _active_dialog(wiki_page)
    dialog.get_by_role("option").nth(0).click()
    label = dialog.get_by_role("textbox", name="Link text")
    label.fill("A | B }}")
    dialog.get_by_role("button", name="Insert", exact=True).click()
    dialog.wait_for(state="hidden")

    generated = wiki_page.locator("#wpTextbox1").input_value()
    assert "A | B }}" in _render_wikitext(generated)


def test_visual_picker_replaces_exact_link_identity(wiki_page: Page) -> None:
    _open_visual_editor(wiki_page)
    manual = wiki_page.locator('[typeof~="mw:Transclusion"].erenshor-link', has_text="Manual Ability Text")
    manual.click(force=True)
    _open_visual_picker(wiki_page)

    dialog = _active_dialog(wiki_page)
    dialog.wait_for()
    search = dialog.get_by_role("combobox", name="Search")
    search.fill("flame bolt")
    result = dialog.locator('[role="option"][data-erenshor-key="spell:flame_bolt_greater"]')
    result.wait_for()
    result.click()
    assert dialog.get_by_role("textbox", name="Link text").input_value() == "Manual Ability Text"
    dialog.get_by_role("button", name="Replace", exact=True).click()
    dialog.wait_for(state="hidden")
    _wait_for_visual_key(wiki_page, "spell:flame_bolt_greater")

    assert _visual_template_params(wiki_page, "spell:flame_bolt_greater") == [
        {
            "stablekey": "spell:flame_bolt_greater",
            "text": "Manual Ability Text",
        }
    ]
    assert not any(
        params.get("text") == "Manual Ability Text"
        for params in _visual_template_params(wiki_page, "spell:minor_lightning")
    )
