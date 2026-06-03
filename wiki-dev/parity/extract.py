"""Render pages in a real browser and extract parity properties.

This is the only browser-dependent module. It loads each page in Chromium via
Playwright, waits for MediaWiki ResourceLoader and the DataTables gadget to
settle, and extracts the computed properties declared by the contract. It is
validated against the running local stack and the live wiki rather than by unit
tests, which target the pure ``compare`` module.
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
    """Navigate and wait for MediaWiki readiness, retrying transient timeouts.
    The live wiki occasionally serves a harder Cloudflare challenge that delays
    ResourceLoader past one timeout. The clearance cookie persists in the
    browser context, so a reload after the first attempt succeeds.
    """
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


def _extract_page(page: Page, url: str, targets: Sequence[Target]) -> dict[str, dict[str, str]]:
    _navigate_until_ready(page, url)
    specs: list[dict[str, object]] = [
        {"name": target.name, "selector": target.selector, "properties": list(target.properties)} for target in targets
    ]
    result: dict[str, dict[str, str]] = page.evaluate(_EXTRACT_JS, specs)
    return result


def extract_snapshot(pages: Sequence[tuple[str, str, Sequence[Target]]], *, headless: bool = True) -> Snapshot:
    """Render each ``(scope_name, url, targets)`` and return a parity snapshot.
    Each page is rendered in its own freshly launched browser. The live wiki's
    Cloudflare challenge is reliably cleared by a fresh foreground browser but
    not by a second navigation in a reused one, and ``pages`` is short, so a
    browser per page keeps capture robust. ``pages`` is built by the runner so
    this module stays agnostic to live vs local URL conventions.
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
