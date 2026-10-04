"""Compare live page renders with a repository page in TemplateSandbox."""

from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Protocol

import mwparserfromhell

if TYPE_CHECKING:
    from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
    from erenshor.infrastructure.wiki.client import MediaWikiParse


@dataclass(frozen=True, slots=True)
class RenderDifference:
    title: str
    removed: tuple[str, ...]
    added: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RenderCheck:
    title: str
    users: int
    checked: tuple[str, ...]
    differences: tuple[RenderDifference, ...]
    provisional: bool = False


class RenderCheckError(ValueError):
    """A new script error or missing template blocks the repository page."""


class _VisibleHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible: list[str] = []
        self.errors: list[str] = []
        self._hidden = 0
        self._error = 0
        self._elements: list[tuple[str, bool, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = attributes.get("class") or ""
        style = (attributes.get("style") or "").replace(" ", "").casefold()
        hidden = tag in {"script", "style"} or "display:none" in style
        error = "scribunto-error" in classes.split()
        if tag not in {"br", "hr", "img", "input", "meta", "link", "wbr"}:
            self._elements.append((tag, hidden, error))
            self._hidden += hidden
            self._error += error
        if not self._hidden and tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.visible.append("\n")

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._elements) - 1, -1, -1):
            if self._elements[index][0] == tag:
                for _, hidden, error in self._elements[index:]:
                    self._hidden -= hidden
                    self._error -= error
                del self._elements[index:]
                break
        if not self._hidden and tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.visible.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.visible.append(data)
            if self._error:
                self.errors.append(data)

    def lines(self) -> tuple[str, ...]:
        return tuple(line for raw in "".join(self.visible).splitlines() if (line := " ".join(raw.split())))


def _html(parse: MediaWikiParse) -> _VisibleHTML:
    result = _VisibleHTML()
    result.feed(parse.html)
    return result


def page_features(text: str, catalog: Mapping[str, LinkCatalogEntry]) -> frozenset[tuple[str, ...]]:
    """Collect template calls and filled parameter and entity variants."""
    features: set[tuple[str, ...]] = set()
    for template in mwparserfromhell.parse(text).filter_templates(recursive=True):
        name = str(template.name).strip().replace("_", " ").casefold()
        features.add(("template", name))
        for parameter in template.params:
            value = str(parameter.value).strip()
            if not value:
                continue
            key = str(parameter.name).strip().casefold()
            features.add(("parameter", name, key))
            if key in {"type", "kind"}:
                features.add(("value", key, value.casefold()))
            if key == "stablekey":
                identity = catalog.get(value.casefold())
                if identity is not None:
                    features.add(("entity", identity.kind, identity.subtype or ""))
    return frozenset(features)


def select_render_pages(
    texts: Mapping[str, str], catalog: Mapping[str, LinkCatalogEntry], *, full: bool = False
) -> tuple[str, ...]:
    """Select a greedy title-stable cover, or all user pages."""
    if full:
        return tuple(sorted(texts))
    features = {title: page_features(text, catalog) for title, text in texts.items()}
    uncovered = set().union(*features.values()) if features else set()
    selected: list[str] = []
    while uncovered:
        title = max(sorted(set(texts) - set(selected)), key=lambda candidate: len(features[candidate] & uncovered))
        selected.append(title)
        uncovered -= features[title]
    if texts and not selected:
        selected.append(min(texts))
    return tuple(selected)


def check_render(
    client: object,
    title: str,
    new_text: str,
    *,
    catalog: Mapping[str, LinkCatalogEntry],
    live_cache: dict[str, MediaWikiParse],
    full: bool = False,
    provisional: bool = False,
) -> RenderCheck:
    """Parse selected users twice and reject regressions in their renders."""
    from typing import cast

    class _Reader(Protocol):
        def get_embeddedin_pages(self, title: str, namespaces: Sequence[int] = (0,)) -> tuple[str, ...]: ...
        def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]: ...
        def parse_wikitext(
            self,
            title: str,
            text: str,
            *,
            sandbox_title: str | None = None,
            sandbox_text: str | None = None,
            sandbox_content_model: str | None = None,
        ) -> MediaWikiParse: ...

    reader = cast("_Reader", client)
    users = sorted(set(reader.get_embeddedin_pages(title, namespaces=(0,))))
    if not users:
        return RenderCheck(title, 0, (), (), provisional)
    texts: dict[str, str] = {}
    for start in range(0, len(users), 50):
        batch = users[start : start + 50]
        pages = reader.get_pages(batch)
        for user in batch:
            text = pages.get(user)
            if text is None:
                raise ValueError(f"{title}: missing text for user page {user}")
            texts[user] = text
    selected = select_render_pages(texts, catalog, full=full)
    differences: list[RenderDifference] = []
    for user in selected:
        live = live_cache.get(user)
        if live is None:
            live = reader.parse_wikitext(user, texts[user])
            live_cache[user] = live
        sandbox = reader.parse_wikitext(
            user,
            texts[user],
            sandbox_title=title,
            sandbox_text=new_text,
            sandbox_content_model="Scribunto" if title.startswith("Module:") else "wikitext",
        )
        old_html, new_html = _html(live), _html(sandbox)
        old_errors = {" ".join(error.split()) for error in old_html.errors if error.strip()}
        new_errors = {" ".join(error.split()) for error in new_html.errors if error.strip()}
        old_missing = {template.title for template in live.templates if not template.exists}
        new_missing = {template.title for template in sandbox.templates if not template.exists}
        problems = ["script error" for _ in new_errors - old_errors]
        problems.extend(f"missing template {missing}" for missing in sorted(new_missing - old_missing))
        if problems:
            raise RenderCheckError(f"{title} blocked on {user}: {', '.join(problems)}")
        old_lines, new_lines = old_html.lines(), new_html.lines()
        old_categories = {category.title for category in live.categories}
        new_categories = {category.title for category in sandbox.categories}
        if old_lines != new_lines or old_categories != new_categories:
            changes = tuple(difflib.ndiff(old_lines, new_lines))
            removed = tuple(line[2:] for line in changes if line.startswith("- ")) + tuple(
                f"Category:{category.removeprefix('Category:')}" for category in sorted(old_categories - new_categories)
            )
            added = tuple(line[2:] for line in changes if line.startswith("+ ")) + tuple(
                f"Category:{category.removeprefix('Category:')}" for category in sorted(new_categories - old_categories)
            )
            differences.append(RenderDifference(user, removed, added))
    return RenderCheck(title, len(users), selected, tuple(differences), provisional)
