"""Dependency-derived refresh of pages that transclude repo-owned templates/modules.

After repo-owned templates or data modules deploy, the pages that transclude
them keep stale link, category, and Cargo data until each dependent page is
reparsed. Template/module dependents are discovered through MediaWiki's
embeddedin API and purged with ``forcelinkupdate``; item-owned relationship
pages are explicitly null-edited before purging so their Cargo rows are
rewritten.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

EditAssertion = Literal["user", "bot"]


ITEM_OWNERSHIP_SOURCE_TYPES = {
    "loot_drops": {"ObtainedFrom": {"drop"}},
    "character_vendor_items": {"ObtainedFrom": {"vendor"}},
    "character_dialogs": {"ObtainedFrom": {"dialog"}},
    "quest_variants": {"ObtainedFrom": {"quest"}, "UsedIn": {"quest_requirement"}},
    "crafting_recipes": {"ObtainedFrom": {"craft"}, "UsedIn": {"craft_material"}},
    "mining_nodes": {"ObtainedFrom": {"mining"}},
    "water_fishables": {"ObtainedFrom": {"fishing"}},
    "item_bags": {"ObtainedFrom": {"item_bag"}},
    "item_drops": {"ObtainedFrom": {"item_use"}},
    "spell_created_items": {"ObtainedFrom": {"item_use"}},
    "class_starting_items": {"ObtainedFrom": {"starting"}},
    "smithing_special_uses": {"UsedIn": {"upgrade_material", "blessing_removal_material"}},
}


class WikiEmbeddedRefreshClient(Protocol):
    """MediaWiki operations required to refresh transcluding pages."""

    def query_cargo_table(
        self,
        tables: str,
        fields: str,
        where: str | None = None,
        limit: int = 50,
        offset: int | None = None,
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> list[dict[str, object]]: ...

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]: ...

    def null_edit_pages(
        self,
        titles: Sequence[str],
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]: ...

    def purge_pages(
        self,
        titles: Sequence[str],
        force_link_update: bool = True,
        force_recursive_link_update: bool = False,
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class EmbeddedRefreshResult:
    """Result of a dependency-derived refresh pass."""

    requested: tuple[str, ...]
    refreshed: tuple[str, ...]


def refresh_embedded_pages(
    *,
    client: WikiEmbeddedRefreshClient,
    dependency_titles: tuple[str, ...],
    namespaces: tuple[int, ...],
    assertion: EditAssertion,
    assert_user: str | None = None,
) -> EmbeddedRefreshResult:
    """Refresh every page that transcludes any of the given dependencies."""
    target_titles: set[str] = set()
    for dependency_title in dependency_titles:
        target_titles.update(
            client.get_embeddedin_pages(
                dependency_title,
                namespaces=namespaces,
                assertion=assertion,
                assert_user=assert_user,
            )
        )

    requested = tuple(sorted(target_titles))
    if not requested:
        return EmbeddedRefreshResult(requested=(), refreshed=())

    refreshed = client.purge_pages(
        requested,
        force_link_update=True,
        assertion=assertion,
        assert_user=assert_user,
    )
    return EmbeddedRefreshResult(requested=requested, refreshed=tuple(refreshed))


def refresh_item_owners_for_source_changes(
    *,
    client: WikiEmbeddedRefreshClient,
    changed_source_tables: Sequence[str],
    assertion: EditAssertion,
    assert_user: str | None = None,
) -> EmbeddedRefreshResult:
    """Reparse item pages whose Cargo rows are owned by items.

    Source-side data changes do not make the source page a Cargo owner: the
    ``ObtainedFrom``/``UsedIn`` rows are rewritten only when their item page is
    parsed. Querying both relation tables discovers the complete owning-page set
    after any relevant source table changes.
    """
    relation_types: dict[str, set[str]] = {"ObtainedFrom": set(), "UsedIn": set()}
    for source_table in changed_source_tables:
        for relation_table, source_types in ITEM_OWNERSHIP_SOURCE_TYPES.get(source_table, {}).items():
            relation_types[relation_table].update(source_types)
    if not any(relation_types.values()):
        return EmbeddedRefreshResult(requested=(), refreshed=())

    target_titles: set[str] = set()
    for relation_table in ("ObtainedFrom", "UsedIn"):
        types = relation_types[relation_table]
        if not types:
            continue
        offset = 0
        while True:
            field_name = "SourceType" if relation_table == "ObtainedFrom" else "UseType"
            quoted_types = ",".join(f'"{source_type}"' for source_type in sorted(types))
            rows = client.query_cargo_table(
                tables=relation_table,
                fields="_pageName=Page",
                where=f"{field_name} IN ({quoted_types})",
                assertion=assertion,
                assert_user=assert_user,
                limit=500,
                offset=offset,
            )
            for row in rows:
                title = row.get("title")
                if isinstance(title, dict):
                    page = title.get("Page")
                    if isinstance(page, str) and page:
                        target_titles.add(page)
            if len(rows) < 500:
                break
            offset += len(rows)

    requested = tuple(sorted(target_titles))
    if not requested:
        return EmbeddedRefreshResult(requested=(), refreshed=())

    reparsed = client.null_edit_pages(requested, assertion=assertion, assert_user=assert_user)
    client.purge_pages(
        requested,
        force_link_update=True,
        assertion=assertion,
        assert_user=assert_user,
    )
    return EmbeddedRefreshResult(requested=requested, refreshed=tuple(reparsed))
