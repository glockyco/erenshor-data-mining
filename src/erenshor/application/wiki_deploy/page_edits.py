"""Plan reviewed one-time text edits of live pages.

A one-time edit changes text that people own, for example a wrong sentence
that generation cannot reach. Each edit names the exact live text it replaces,
so a page that changed since the review fails instead of being overwritten.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from erenshor.application.wiki_deploy.articles import parse_problems
from erenshor.application.wiki_deploy.guarded_edits import GuardedPageEdit

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from erenshor.application.wiki_deploy.manifest import ContentModel
    from erenshor.infrastructure.wiki import MediaWikiPageSnapshot, MediaWikiParse


class PageEditError(ValueError):
    """A reviewed edit cannot be planned against the live page."""


@dataclass(frozen=True, slots=True)
class TextReplacement:
    old: str
    new: str


@dataclass(frozen=True, slots=True)
class PageEditRequest:
    title: str
    summary: str
    replacements: tuple[TextReplacement, ...]


class PageEditClient(Protocol):
    def get_page_snapshots(self, titles: Sequence[str]) -> Mapping[str, MediaWikiPageSnapshot]: ...

    def parse_wikitext(self, title: str, text: str) -> MediaWikiParse: ...


def load_page_edit_requests(path: Path) -> tuple[PageEditRequest, ...]:
    """Read the reviewed edits of a TOML file.

    Each ``[[pages]]`` entry has a ``title``, an edit ``summary``, and one or
    more ``[[pages.replace]]`` entries with the exact ``old`` text and its
    ``new`` text.
    """
    return parse_page_edit_requests(path.read_bytes(), source=str(path))


def parse_page_edit_requests(content: bytes, *, source: str) -> tuple[PageEditRequest, ...]:
    """Parse captured TOML bytes without rereading their source."""
    data = tomllib.loads(content.decode("utf-8"))
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise PageEditError(f"{source} lists no [[pages]]")
    requests: list[PageEditRequest] = []
    for page in pages:
        title = page.get("title")
        summary = page.get("summary")
        if not isinstance(title, str) or not title.strip():
            raise PageEditError(f"{source}: a page has no title")
        if not isinstance(summary, str) or not summary.strip():
            raise PageEditError(f"{source}: {title} has no summary")
        replacements: list[TextReplacement] = []
        for replacement in page.get("replace") or []:
            old, new = replacement.get("old"), replacement.get("new")
            if not isinstance(old, str) or not old or not isinstance(new, str) or old == new:
                raise PageEditError(f"{source}: {title} has a replacement without a changed text")
            replacements.append(TextReplacement(old, new))
        if not replacements:
            raise PageEditError(f"{source}: {title} has no [[pages.replace]]")
        requests.append(PageEditRequest(title, summary, tuple(replacements)))
    titles = [request.title for request in requests]
    if len(set(titles)) != len(titles):
        raise PageEditError(f"{source} lists a page twice")
    return tuple(requests)


def plan_page_edits(requests: Sequence[PageEditRequest], client: PageEditClient) -> tuple[GuardedPageEdit, ...]:
    """Apply each replacement to the live text, which must hold each old text exactly once."""
    snapshots = client.get_page_snapshots([request.title for request in requests])
    edits: list[GuardedPageEdit] = []
    for request in requests:
        snapshot = snapshots.get(request.title)
        if snapshot is None or snapshot.source_text is None or snapshot.revision is None:
            raise PageEditError(f"{request.title} does not exist")
        if snapshot.content_model not in ("wikitext", "Scribunto", "sanitized-css"):
            raise PageEditError(f"{request.title} has an unsupported or missing content model")
        text = snapshot.source_text
        for replacement in request.replacements:
            count = text.count(replacement.old)
            if count != 1:
                raise PageEditError(f"{request.title} holds the text {count} times, not once: {replacement.old[:80]!r}")
            text = text.replace(replacement.old, replacement.new, 1)
        edits.append(
            GuardedPageEdit(
                request.title,
                request.summary,
                text,
                snapshot.source_text,
                snapshot.revision,
                content_model=cast("ContentModel", snapshot.content_model),
            )
        )
    return tuple(edits)


def render_problems(edit: GuardedPageEdit, client: PageEditClient) -> tuple[str, ...]:
    """Return what the new text would break on the page that the live text does not."""
    live_categories = frozenset(
        category.title for category in client.parse_wikitext(edit.title, edit.original).categories
    )
    return parse_problems(client.parse_wikitext(edit.title, edit.content), live_categories)
