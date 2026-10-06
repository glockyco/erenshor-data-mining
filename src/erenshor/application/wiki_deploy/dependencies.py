"""Order repository pages and check the pages that they load by literal title against live pages."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Protocol

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry, stage_rank

_INVOKE = re.compile(r"\{\{\s*#invoke\s*:\s*([^|{}]+)\s*\|", re.IGNORECASE)
_LUA_LOAD = re.compile(r"\b(?:require|mw\.loadData)\s*\(\s*(['\"])(Module:[^'\"]+)\1\s*\)")
_TEMPLATE_STYLES = re.compile(r"<templatestyles\s+src\s*=\s*([\"']?)([^\"'>]+?)\1\s*/?>", re.IGNORECASE)
_LUA_STYLES_POSITIONAL = re.compile(
    r"\bextensionTag\s*\(\s*(['\"])templatestyles\1\s*,\s*(['\"])[^'\"]*\2\s*,\s*"
    r"\{[^{}]*?\bsrc\s*=\s*(['\"])([^'\"]+)\3",
)
_LUA_STYLES_TABLE = re.compile(
    r"\bextensionTag\s*(?:\(\s*)?\{\s*name\s*=\s*(['\"])templatestyles\1\s*,\s*"
    r"args\s*=\s*\{[^{}]*?\bsrc\s*=\s*(['\"])([^'\"]+)\2",
)


def _stylesheet_title(source: str) -> str:
    """The page that a ``<templatestyles src>`` names: TemplateStyles assumes Template: without a namespace."""
    name = source.strip().replace("_", " ")
    namespace, separator, _ = name.partition(":")
    return name if separator and namespace and "/" not in namespace else f"Template:{name}"


def literal_dependencies(title: str, text: str) -> tuple[str, ...]:
    """The pages that a page loads by literal title.

    A Lua module loads modules through ``require`` and ``mw.loadData`` and
    stylesheets through literal ``extensionTag`` calls. A wikitext page loads
    modules through ``#invoke`` and stylesheets through ``<templatestyles src>``.
    """
    if title.startswith("Module:"):
        modules = {match.group(2).strip().replace("_", " ") for match in _LUA_LOAD.finditer(text)}
        stylesheets = {
            _stylesheet_title(match.group(group))
            for pattern, group in ((_LUA_STYLES_POSITIONAL, 4), (_LUA_STYLES_TABLE, 3))
            for match in pattern.finditer(text)
        }
        return tuple(sorted(modules | stylesheets))
    modules = {
        name if name.startswith("Module:") else f"Module:{name}"
        for match in _INVOKE.finditer(text)
        if (name := match.group(1).strip().replace("_", " "))
    }
    stylesheets = {_stylesheet_title(match.group(2)) for match in _TEMPLATE_STYLES.finditer(text)}
    return tuple(sorted(modules | stylesheets))


def order_and_check_dependencies(
    manifest: RepoWikiPageManifest,
    source_texts: Mapping[str, str],
    live_texts: Mapping[str, str | None],
) -> RepoWikiPageManifest:
    """Fail on a missing dependency or cycle and order dependencies before their users inside each stage."""
    by_title = {entry.title: entry for entry in manifest.entries}
    ordered: list[RepoWikiPageManifestEntry] = []
    visiting: set[str] = set()
    completed: set[str] = set()
    written: set[str] = set()

    def visit(title: str, root: str) -> None:
        if title in completed:
            return
        if title in visiting:
            raise ValueError(f"{root} has a dependency cycle at {title}")
        visiting.add(title)
        text = source_texts[title] if title in by_title else live_texts.get(title)
        if text is None:
            raise ValueError(f"{root} needs missing page {title}")
        for dependency in literal_dependencies(title, text):
            planned = by_title.get(dependency)
            if planned is not None and stage_rank(planned.upload_stage) <= stage_rank(by_title[root].upload_stage):
                visit(dependency, root)
            elif dependency not in written and live_texts.get(dependency) is None:
                raise ValueError(f"{root} needs missing page {dependency}")
            else:
                visit_live(dependency, root)
        visiting.remove(title)
        completed.add(title)
        if title in by_title:
            ordered.append(by_title[title])
            written.add(title)

    checked_live: set[str] = set()
    live_visiting: set[str] = set()

    def visit_live(title: str, root: str) -> None:
        if title in checked_live or title in written:
            return
        if title in live_visiting:
            return
        text = live_texts.get(title)
        if text is None:
            raise ValueError(f"{root} needs missing page {title}")
        live_visiting.add(title)
        for dependency in literal_dependencies(title, text):
            if dependency in by_title and (
                stage_rank(by_title[dependency].upload_stage) <= stage_rank(by_title[root].upload_stage)
            ):
                visit(dependency, root)
            else:
                visit_live(dependency, root)
        live_visiting.remove(title)
        checked_live.add(title)

    for entry in manifest.entries:
        visit(entry.title, entry.title)
    return RepoWikiPageManifest(entries=tuple(ordered))


def needed_live_dependencies(source_texts: Mapping[str, str], client: object) -> dict[str, str | None]:
    """Fetch the transitive live dependencies in batches, including missing titles."""
    from typing import cast

    class _Reader(Protocol):
        def get_pages(self, titles: Sequence[str]) -> dict[str, str | None]: ...

    reader = cast("_Reader", client)
    pending = {dependency for title, text in source_texts.items() for dependency in literal_dependencies(title, text)}
    seen: dict[str, str | None] = {}
    while pending:
        batch = sorted(pending - seen.keys())
        if not batch:
            break
        fetched = reader.get_pages(batch)
        if set(fetched) != set(batch):
            raise ValueError(f"Missing live module response for {next(iter(set(batch) - fetched.keys()))}")
        seen.update(fetched)
        pending = {
            dependency
            for title, text in seen.items()
            if text is not None and title not in source_texts
            for dependency in literal_dependencies(title, text)
        } - seen.keys()
    return seen
