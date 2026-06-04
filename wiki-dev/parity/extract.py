"""Render pages in a real browser and extract parity properties.

This is the only browser-dependent module. URL extraction loads local pages in
Chromium via Playwright, waits for MediaWiki ResourceLoader and the DataTables
gadget to settle, and extracts the computed properties declared by the contract.
HTML extraction renders already-parsed live HTML with local stylesheets, avoiding
Cloudflare-protected browser routes during baseline capture.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from .compare import Snapshot
    from .contract import Target

VIEWPORT = {"width": 1280, "height": 900}
READY_TIMEOUT_MS = 30000
READY_ATTEMPTS = 3

_READY_JS = """
() => {
  if (!window.mw || !mw.loader) return false;
  if (mw.loader.getState('site') !== 'ready') return false;
  if (mw.loader.getState('ext.gadget.datatables') !== 'ready') return false;
  return true;
}
"""

_EXTRACT_JS = """
(specs) => {
  const out = {};
  for (const spec of specs) {
    const el = document.querySelector(spec.selector);
    if (!el) continue;
    const props = {};
    for (const key of spec.properties) {
      if (key.startsWith('@class:')) {
        props[key] = el.classList.contains(key.slice(7)) ? 'true' : 'false';
      } else if (key.startsWith('@module:')) {
        props[key] = window.mw ? (mw.loader.getState(key.slice(8)) || 'null') : 'no-mw';
      } else {
        props[key] = getComputedStyle(el).getPropertyValue(key).trim();
      }
    }
    out[spec.name] = props;
  }
  return out;
}
"""


def _navigate_until_ready(page: Page, url: str) -> None:
    """Navigate and wait for local MediaWiki readiness."""
    last_error: PlaywrightTimeoutError | None = None
    for _ in range(READY_ATTEMPTS):
        page.bring_to_front()
        page.goto(url, wait_until="load")
        try:
            page.wait_for_function(_READY_JS, timeout=READY_TIMEOUT_MS, polling=500)
        except PlaywrightTimeoutError as error:
            last_error = error
            continue
        return
    raise RuntimeError(f"Page never reached MediaWiki readiness: {url}") from last_error


def _target_specs(targets: Sequence[Target]) -> list[dict[str, object]]:
    return [
        {"name": target.name, "selector": target.selector, "properties": list(target.properties)} for target in targets
    ]


def _extract_targets(page: Page, targets: Sequence[Target]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = page.evaluate(_EXTRACT_JS, _target_specs(targets))
    return result


def _extract_page(page: Page, url: str, targets: Sequence[Target]) -> dict[str, dict[str, str]]:
    _navigate_until_ready(page, url)
    return _extract_targets(page, targets)


def _extract_html(page: Page, html: str, targets: Sequence[Target]) -> dict[str, dict[str, str]]:
    page.set_content(html, wait_until="networkidle")
    return _extract_targets(page, targets)


def extract_snapshot(pages: Sequence[tuple[str, str, Sequence[Target]]], *, headless: bool = True) -> Snapshot:
    """Render each ``(scope_name, url, targets)`` and return a parity snapshot.
    URL extraction is used for local checks. Source-based live capture uses
    ``extract_html_snapshot`` so it never navigates Chromium to
    Cloudflare-protected live wiki pages.
    """
    snapshot: Snapshot = {}
    with sync_playwright() as playwright:
        for scope_name, url, targets in pages:
            browser = playwright.chromium.launch(headless=headless)
            try:
                page = browser.new_context(viewport=VIEWPORT).new_page()
                snapshot[scope_name] = _extract_page(page, url, targets)
            finally:
                browser.close()
    return snapshot


def extract_html_snapshot(pages: Sequence[tuple[str, str, Sequence[Target]]], *, headless: bool = True) -> Snapshot:
    """Render each ``(scope_name, html, targets)`` static document snapshot."""
    snapshot: Snapshot = {}
    with sync_playwright() as playwright:
        for scope_name, html, targets in pages:
            browser = playwright.chromium.launch(headless=headless)
            try:
                page = browser.new_context(viewport=VIEWPORT).new_page()
                snapshot[scope_name] = _extract_html(page, html, targets)
            finally:
                browser.close()
    return snapshot
