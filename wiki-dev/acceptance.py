#!/usr/bin/env python3
"""Deterministic acceptance snapshots for the isolated local wiki."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, ModuleType

import httpx

SCHEMA_VERSION = 1
BROWSER_COUNTER_KEYS = ("collected", "deselected", "skipped", "failed", "exit_code")


def _load_helper(filename: str) -> ModuleType:
    """Load a sibling wiki-dev helper without relying on package imports."""
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(f"wiki_dev_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_import_pages = _load_helper("import_pages.py")
_smoke_mediawiki = _load_helper("smoke/mediawiki.py")
_smoke_render = _load_helper("smoke/render.py")

# These aliases are intentional.  Apart from keeping this module a thin
# composition layer, they make the API straightforward to fake in focused
# tests.
discover_pages = _import_pages.discover_pages
query_remote_pages = _import_pages.query_remote_pages
api_url = _import_pages.api_url
parse_page = _smoke_mediawiki.parse_page
check_rendered_html = _smoke_render.check_rendered_html
load_expectations = _smoke_render.load_expectations


@dataclass(frozen=True, slots=True)
class WikiAcceptanceSnapshot:
    """Immutable, comparable state captured from one local wiki instance."""

    managed_pages: Mapping[str, Mapping[str, str]]
    lua_modules: tuple[str, ...]
    interface_gadgets: tuple[str, ...]
    smoke_results: Mapping[str, str]
    browser_counters: Mapping[str, int]

    def __post_init__(self) -> None:
        managed = {
            str(title): MappingProxyType({str(k): str(v) for k, v in sorted(details.items())})
            for title, details in sorted(self.managed_pages.items())
        }
        smoke = {str(title): str(value) for title, value in sorted(self.smoke_results.items())}
        counters = {str(key): int(value) for key, value in sorted(self.browser_counters.items())}
        object.__setattr__(self, "managed_pages", MappingProxyType(managed))
        object.__setattr__(self, "lua_modules", tuple(sorted(self.lua_modules)))
        object.__setattr__(self, "interface_gadgets", tuple(sorted(self.interface_gadgets)))
        object.__setattr__(self, "smoke_results", MappingProxyType(smoke))
        object.__setattr__(self, "browser_counters", MappingProxyType(counters))

    @property
    def interface_pages(self) -> tuple[str, ...]:
        """Return the managed MediaWiki interface and gadget titles."""
        return self.interface_gadgets

    def to_payload(self) -> dict[str, object]:
        """Return a stable JSON-compatible representation of the snapshot."""
        return {
            "schema_version": SCHEMA_VERSION,
            "managed_pages": {title: dict(details) for title, details in self.managed_pages.items()},
            "lua_modules": list(self.lua_modules),
            "interface_gadgets": list(self.interface_gadgets),
            "smoke_results": dict(self.smoke_results),
            "browser_counters": dict(self.browser_counters),
        }

    def to_json(self) -> str:
        """Serialize this snapshot with stable key and separator choices."""
        return json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))


def _validate_browser_counters(browser: Mapping[str, int]) -> dict[str, int]:
    if set(browser) != set(BROWSER_COUNTER_KEYS):
        missing = sorted(set(BROWSER_COUNTER_KEYS) - set(browser))
        extra = sorted(set(browser) - set(BROWSER_COUNTER_KEYS))
        raise ValueError(
            f"Browser counters must contain exactly {BROWSER_COUNTER_KEYS}; missing={missing}, extra={extra}"
        )
    counters: dict[str, int] = {}
    for key in BROWSER_COUNTER_KEYS:
        value = browser[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Browser counter {key!r} must be a nonnegative integer")
        counters[key] = value
    return counters


def capture_acceptance(root: Path, base_url: str, browser: Mapping[str, int]) -> WikiAcceptanceSnapshot:
    """Capture managed pages, smoke output, and browser counters locally."""
    pages = list(discover_pages(root))
    endpoint = api_url(base_url)
    counters = _validate_browser_counters(browser)
    titles = [page.title for page in pages]
    expectations = load_expectations(root / "wiki-dev" / "fixtures" / "smoke.tsv")
    with httpx.Client() as client:
        remote = query_remote_pages(client, endpoint, titles)
        managed: dict[str, Mapping[str, str]] = {}
        for page in pages:
            state = remote.get(page.title)
            if state is None:
                raise RuntimeError(f"Managed page is missing: {page.title}")
            if state.content_model != page.content_model:
                raise RuntimeError(
                    f"Managed page content model mismatch for {page.title}: "
                    f"expected {page.content_model}, got {state.content_model}"
                )
            managed[page.title] = {
                "content_model": state.content_model,
                "sha256": hashlib.sha256(state.content.encode("utf-8")).hexdigest(),
            }
        smoke_results: dict[str, str] = {}
        for title, expected in sorted(expectations.items()):
            result = check_rendered_html(title, parse_page(client, endpoint, title), expected)
            if not result.ok:
                raise RuntimeError(f"Smoke check failed for {title}: {result.missing}")
            signature = json.dumps(
                {"expected": expected, "missing": result.missing, "ok": result.ok},
                sort_keys=True,
                separators=(",", ":"),
            )
            smoke_results[title] = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return WikiAcceptanceSnapshot(
        managed_pages=managed,
        lua_modules=tuple(page.title for page in pages if page.title.startswith("Module:")),
        interface_gadgets=tuple(page.title for page in pages if page.title.startswith("MediaWiki:")),
        smoke_results=smoke_results,
        browser_counters=counters,
    )


def _diff_values(left: object, right: object, path: str, output: list[str]) -> None:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        for key in sorted(set(left) | set(right), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                output.append(child)
            else:
                _diff_values(left[key], right[key], child, output)
        return
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        for index in range(max(len(left), len(right))):
            child = f"{path}[{index}]"
            if index >= len(left) or index >= len(right):
                output.append(child)
            else:
                _diff_values(left[index], right[index], child, output)
        return
    if left != right:
        output.append(path)


def compare_acceptance(warm: WikiAcceptanceSnapshot, clean: WikiAcceptanceSnapshot) -> list[str]:
    """Return deterministic human-readable paths for every snapshot difference."""
    differences: list[str] = []
    _diff_values(warm.to_payload(), clean.to_payload(), "", differences)
    return differences


__all__ = [
    "BROWSER_COUNTER_KEYS",
    "SCHEMA_VERSION",
    "WikiAcceptanceSnapshot",
    "capture_acceptance",
    "compare_acceptance",
]
