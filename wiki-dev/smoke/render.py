"""Rendered-page smoke expectations for the local MediaWiki harness.

Each expectation selects a location in the rendered page by a small selector
grammar instead of pinning a literal substring of the raw HTML:

``category:NAME``
    The page belongs to the category NAME exactly.
``category*:FRAGMENT``
    The page belongs to some category whose name contains FRAGMENT.
``heading:TEXT``
    Some ``h1``-``h4`` element's text contains TEXT.
``infobox:TEXT``
    Some element inside the page's portable infobox contains TEXT.
``text:TEXT``
    The page's visible text (scripts and styles excluded) contains TEXT.
``elem:SELECTOR``
    An element matches SELECTOR, a compound CSS-like selector of the form
    ``tag?(.class)*(#id)?([attr]|[attr="value"]|[attr*="value"])*(=TEXT)?``.
    Omitting ``=TEXT`` checks only that a matching element exists; including
    it also requires the element's own and descendant text to contain TEXT.

Any selector may be prefixed with ``!`` to require that it does not match.
"""

from __future__ import annotations

import html as html_lib
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from .mediawiki import ParsedPage


class SmokeResult(NamedTuple):
    """Result for one rendered-page expectation check."""

    title: str
    ok: bool
    missing: list[str]


FORBIDDEN_HTML_MARKERS = (
    ("Lua error", "forbidden parser output: Lua error"),
    ("Script error", "forbidden parser output: Script error"),
    ('class="error"', "forbidden parser output: parser error"),
    ('&lt;aside class="portable-infobox', "forbidden parser output: escaped PortableInfobox shell"),
    ('&lt;section class="pi-item', "forbidden parser output: escaped PortableInfobox section"),
    ("&lt;thead&gt;", "forbidden parser output: escaped table header section"),
    ("&lt;tbody&gt;", "forbidden parser output: escaped table body section"),
    ("{{ItemLink|", "forbidden parser output: raw cross-reference template"),
    ("{{AbilityLink|", "forbidden parser output: raw cross-reference template"),
    ("{{QuestLink|", "forbidden parser output: raw cross-reference template"),
    ("{{CharacterLink|", "forbidden parser output: raw cross-reference template"),
    ("{{Item/", "forbidden parser output: raw legacy item template"),
    ("{{FactionLink|", "forbidden parser output: raw cross-reference template"),
    ("{{#if:", "forbidden parser output: raw #if parser function"),
    ("{{#ifeq:", "forbidden parser output: raw #ifeq parser function"),
)

FORBIDDEN_HTML_PATTERNS = (
    (
        re.compile(r'<a\b(?=[^>]*\bclass="[^"]*\bnew\b)(?=[^>]*\btitle="Template:)', re.I),
        "forbidden parser output: unresolved template",
    ),
    (
        re.compile(r"<!--(?:(?!-->).)*\blimit exceeded\b(?:(?!-->).)*-->", re.I | re.S),
        "forbidden parser output: parser limit report",
    ),
)

FORBIDDEN_CATEGORY_PREFIXES = (
    ("Pages_with_missing_Erenshor_", "forbidden parser output: unexpected missing-data category"),
)

_HIDDEN_TAGS = frozenset({"script", "style"})
_VOID_TAGS = frozenset({"br", "hr", "img", "input", "meta", "link", "wbr"})
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4"})


class _Node:
    """One element of a rendered page's DOM, built for selector matching."""

    __slots__ = ("attrs", "children", "own_text", "parent", "tag")

    def __init__(self, tag: str, attrs: dict[str, str], parent: _Node | None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Node | str] = []
        self.parent = parent
        self.own_text: list[str] = []

    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def text(self) -> str:
        """This element's own and descendant text, excluding script and style content."""
        parts = list(self.own_text)
        for child in self.children:
            if isinstance(child, _Node):
                if child.tag in _HIDDEN_TAGS:
                    continue
                parts.append(child.text())
            else:
                parts.append(child)
        return "".join(parts)

    def walk(self) -> list[_Node]:
        out: list[_Node] = [self]
        for child in self.children:
            if isinstance(child, _Node):
                out.extend(child.walk())
        return out


class _DOMBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, None)
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {name: value or "" for name, value in attrs}, self._stack[-1])
        self._stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {name: value or "" for name, value in attrs}, self._stack[-1])
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        current = self._stack[-1]
        current.own_text.append(data)
        current.children.append(data)


def _build_dom(html: str) -> _Node:
    builder = _DOMBuilder()
    builder.feed(html)
    return builder.root


def _visible_text(root: _Node) -> str:
    return root.text()


class _ElemSelector(NamedTuple):
    tag: str | None
    classes: tuple[str, ...]
    elem_id: str | None
    attrs: tuple[tuple[str, str, str], ...]
    text: str | None


_SELECTOR_RE = re.compile(
    r"""^
    (?P<tag>[a-zA-Z][a-zA-Z0-9]*)?
    (?P<rest>(?:\.[a-zA-Z0-9_-]+|\#[a-zA-Z0-9_-]+|\[[a-zA-Z0-9_-]+(?:[*]?=".*?")?\])*)
    (?:=(?P<text>.*))?
    $""",
    re.VERBOSE | re.DOTALL,
)
_SELECTOR_PART_RE = re.compile(
    r"\.(?P<cls>[a-zA-Z0-9_-]+)"
    r"|\#(?P<id>[a-zA-Z0-9_-]+)"
    r'|\[(?P<attr>[a-zA-Z0-9_-]+)(?P<op>[*]?=)?(?:"(?P<val>.*?)")?\]'
)


def _parse_elem_selector(selector: str) -> _ElemSelector:
    match = _SELECTOR_RE.match(selector)
    if not match:
        raise ValueError(f"cannot parse elem selector: {selector!r}")
    classes: list[str] = []
    elem_id: str | None = None
    attrs: list[tuple[str, str, str]] = []
    for part in _SELECTOR_PART_RE.finditer(match.group("rest")):
        if part.group("cls"):
            classes.append(part.group("cls"))
        elif part.group("id"):
            elem_id = part.group("id")
        elif part.group("attr"):
            op = part.group("op") or "?"
            attrs.append((part.group("attr"), op, html_lib.unescape(part.group("val") or "")))
    return _ElemSelector(match.group("tag"), tuple(classes), elem_id, tuple(attrs), match.group("text"))


def _elem_matches(node: _Node, selector: _ElemSelector) -> bool:
    if selector.tag and node.tag != selector.tag:
        return False
    if selector.elem_id and node.attrs.get("id") != selector.elem_id:
        return False
    if any(cls not in node.classes() for cls in selector.classes):
        return False
    return all(_attr_matches(node.attrs.get(attr), op, value) for attr, op, value in selector.attrs)


def _attr_matches(actual: str | None, op: str, value: str) -> bool:
    if actual is None:
        return False
    if op == "=":
        return actual == value
    if op == "*=":
        return value in actual
    return True


def check_elem(root: _Node, selector_str: str) -> bool:
    selector = _parse_elem_selector(selector_str)
    matches = [node for node in root.walk() if node.tag != "#root" and _elem_matches(node, selector)]
    if selector.text is None:
        return bool(matches)
    needle = html_lib.unescape(selector.text)
    return any(needle in node.text() for node in matches)


def check_heading(root: _Node, text: str) -> bool:
    needle = html_lib.unescape(text)
    return any(node.tag in _HEADING_TAGS and needle in node.text() for node in root.walk())


def check_infobox(root: _Node, text: str) -> bool:
    needle = html_lib.unescape(text)
    return any("portable-infobox" in node.classes() and needle in node.text() for node in root.walk())


def check_text(root: _Node, text: str) -> bool:
    return html_lib.unescape(text) in _visible_text(root)


def check_category(categories: tuple[str, ...], name: str) -> bool:
    return name in categories


def check_category_fragment(categories: tuple[str, ...], fragment: str) -> bool:
    return any(fragment in category for category in categories)


def check_selector(root: _Node, categories: tuple[str, ...], selector: str) -> bool:
    """Evaluate one ``[!]kind:payload`` selector against a parsed page."""
    negate = selector.startswith("!")
    body = selector[1:] if negate else selector
    kind, _, payload = body.partition(":")
    if kind == "category":
        result = check_category(categories, payload)
    elif kind == "category*":
        result = check_category_fragment(categories, payload)
    elif kind == "heading":
        result = check_heading(root, payload)
    elif kind == "infobox":
        result = check_infobox(root, payload)
    elif kind == "text":
        result = check_text(root, payload)
    elif kind == "elem":
        result = check_elem(root, payload)
    else:
        raise ValueError(f"unknown selector kind {kind!r} in {selector!r}")
    return (not result) if negate else result


def check_rendered_page(title: str, parsed: ParsedPage, expected: list[str]) -> SmokeResult:
    """Check that expected selectors resolve and that no parser error is present."""
    root = _build_dom(parsed.html)
    missing = [selector for selector in expected if not check_selector(root, parsed.categories, selector)]
    missing.extend(message for marker, message in FORBIDDEN_HTML_MARKERS if marker in parsed.html)
    missing.extend(message for pattern, message in FORBIDDEN_HTML_PATTERNS if pattern.search(parsed.html))
    missing.extend(
        message
        for marker, message in FORBIDDEN_CATEGORY_PREFIXES
        if any(category.startswith(marker) for category in parsed.categories)
        and not any(marker in selector for selector in expected)
    )
    return SmokeResult(title=title, ok=not missing, missing=missing)


def load_expectations(path: Path) -> dict[str, list[str]]:
    """Load rendered-page smoke expectations from a tab-separated file.

    Each non-comment line is: title<TAB>selector. A title may appear
    multiple times to assert multiple selectors.
    """
    expectations: dict[str, list[str]] = {}
    if not path.exists():
        return expectations
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        title, selector = line.split("\t", 1)
        expectations.setdefault(title, []).append(selector)
    return expectations
