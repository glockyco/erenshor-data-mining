"""Order repository pages and check literal module dependencies against live pages."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Protocol

from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry

_INVOKE = re.compile(r"\{\{\s*#invoke\s*:\s*([^|{}]+)\s*\|", re.IGNORECASE)
_LUA_LOAD = re.compile(r"\b(?:require|mw\.loadData)\s*\(\s*(['\"])(Module:[^'\"]+)\1\s*\)")
_STAGES = ("generated_data", "lua_module", "cargo_declaration", "template", "content_page", "article")


def literal_dependencies(title: str, text: str) -> tuple[str, ...]:
    """Find literal module titles in a Lua module or wikitext page."""
    if title.startswith("Module:"):
        return tuple(sorted({match.group(2).strip().replace("_", " ") for match in _LUA_LOAD.finditer(text)}))
    return tuple(
        sorted(
            {
                name if name.startswith("Module:") else f"Module:{name}"
                for match in _INVOKE.finditer(text)
                if (name := match.group(1).strip().replace("_", " "))
            }
        )
    )


def order_and_check_dependencies(
    manifest: RepoWikiPageManifest,
    source_texts: Mapping[str, str],
    live_texts: Mapping[str, str | None],
) -> RepoWikiPageManifest:
    """Fail on a missing dependency or cycle and order modules inside each stage."""
    by_title = {entry.title: entry for entry in manifest.entries}
    stage = {name: index for index, name in enumerate(_STAGES)}
    ordered: list[RepoWikiPageManifestEntry] = []
    visiting: set[str] = set()
    completed: set[str] = set()
    written: set[str] = set()

    def visit(title: str, root: str) -> None:
        if title in completed:
            return
        if title in visiting:
            raise ValueError(f"{root} has a module dependency cycle at {title}")
        visiting.add(title)
        text = source_texts[title] if title in by_title else live_texts.get(title)
        if text is None:
            raise ValueError(f"{root} needs missing module {title}")
        for dependency in literal_dependencies(title, text):
            planned = by_title.get(dependency)
            if planned is not None and stage[planned.upload_stage] <= stage[by_title[root].upload_stage]:
                visit(dependency, root)
            elif dependency not in written and live_texts.get(dependency) is None:
                raise ValueError(f"{root} needs missing module {dependency}")
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
            raise ValueError(f"{root} needs missing module {title}")
        live_visiting.add(title)
        for dependency in literal_dependencies(title, text):
            if dependency in by_title and (
                stage[by_title[dependency].upload_stage] <= stage[by_title[root].upload_stage]
            ):
                visit(dependency, root)
            else:
                visit_live(dependency, root)
        live_visiting.remove(title)
        checked_live.add(title)

    for entry in manifest.entries:
        visit(entry.title, entry.title)
    return RepoWikiPageManifest(entries=tuple(ordered))


def needed_live_modules(source_texts: Mapping[str, str], client: object) -> dict[str, str | None]:
    """Fetch transitive live modules in batches, including missing titles."""
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
