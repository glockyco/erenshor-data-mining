"""Tests for dependency-derived refresh of transcluding pages."""

from __future__ import annotations

import re
from collections.abc import Sequence

from erenshor.application.wiki_deploy.refresh import refresh_embedded_pages


class RecordingRefreshClient:
    def __init__(self, embeddedin: dict[str, tuple[str, ...]]) -> None:
        self.embeddedin = embeddedin
        self.embeddedin_requests: list[tuple[str, tuple[int, ...], str, str | None]] = []
        self.purge_calls: list[tuple[tuple[str, ...], bool, str, str | None]] = []
        self.cargo_rows = {
            "ObtainedFrom": (
                {"title": {"Page": "Ember Longsword"}, "SourceType": "drop"},
                {"title": {"Page": "Abyssal Plate"}, "SourceType": "quest"},
            ),
            "UsedIn": (
                {"title": {"Page": "Ember Longsword"}, "UseType": "craft_material"},
                {"title": {"Page": "Frost Dagger"}, "UseType": "quest_requirement"},
            ),
        }
        self.cargo_requests: list[tuple[str, str, str | None, int, int | None, str, str | None]] = []
        self.null_edit_calls: list[tuple[tuple[str, ...], str, str | None]] = []

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        self.embeddedin_requests.append((title, tuple(namespaces), assertion or "", assert_user))
        return self.embeddedin.get(title, ())

    def query_cargo_table(
        self,
        tables: str,
        fields: str,
        where: str | None = None,
        limit: int = 50,
        offset: int | None = None,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> list[dict[str, object]]:
        self.cargo_requests.append((tables, fields, where, limit, offset, assertion or "", assert_user))
        rows = list(self.cargo_rows.get(tables, ()))
        if where is not None:
            allowed = set(re.findall(r'"([^"]+)"', where))
            rows = [row for row in rows if row.get("SourceType", row.get("UseType")) in allowed]
        return rows[offset or 0 : (offset or 0) + limit]

    def null_edit_pages(
        self,
        titles: Sequence[str],
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        self.null_edit_calls.append((tuple(titles), assertion or "", assert_user))
        return tuple(titles)

    def purge_pages(
        self,
        titles: Sequence[str],
        force_link_update: bool = True,
        force_recursive_link_update: bool = False,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        self.purge_calls.append((tuple(titles), force_link_update, assertion or "", assert_user))
        return tuple(titles)


def test_refresh_embedded_pages_purges_deduplicated_dependents_with_forced_link_update() -> None:
    """Dependents discovered from every dependency are purged once with a forced link update."""
    client = RecordingRefreshClient(
        {
            "Template:Item": ("Ember Longsword", "Abyssal Plate"),
            "Module:Erenshor/Item": ("Ember Longsword", "Frost Dagger"),
        }
    )

    result = refresh_embedded_pages(
        client=client,
        dependency_titles=("Template:Item", "Module:Erenshor/Item"),
        namespaces=(0,),
        assertion="bot",
        assert_user="ErenshorBot",
    )

    # Targets are deduplicated across dependencies and ordered deterministically.
    assert result.requested == ("Abyssal Plate", "Ember Longsword", "Frost Dagger")
    assert result.refreshed == ("Abyssal Plate", "Ember Longsword", "Frost Dagger")
    # Exactly one purge call, forcing a link update under the bot assertion.
    assert len(client.purge_calls) == 1
    purged_titles, force_link_update, assertion, assert_user = client.purge_calls[0]
    assert purged_titles == ("Abyssal Plate", "Ember Longsword", "Frost Dagger")
    assert force_link_update is True
    assert assertion == "bot"
    assert assert_user == "ErenshorBot"


def test_refresh_item_owners_for_source_changes_reparses_relation_owners() -> None:
    from erenshor.application.wiki_deploy.refresh import refresh_item_owners_for_source_changes

    client = RecordingRefreshClient({})
    result = refresh_item_owners_for_source_changes(
        client=client,
        changed_source_tables=("loot_drops",),
        assertion="bot",
        assert_user="ErenshorBot",
    )

    assert result.requested == ("Ember Longsword",)
    assert result.refreshed == result.requested
    assert [request[0] for request in client.cargo_requests] == ["ObtainedFrom"]
    assert 'SourceType IN ("drop")' in (client.cargo_requests[0][2] or "")
    assert client.null_edit_calls == [(result.requested, "bot", "ErenshorBot")]
    assert len(client.purge_calls) == 1
    assert client.purge_calls[0][0] == result.requested


def test_refresh_item_owners_reparses_item_use_sources() -> None:
    from erenshor.application.wiki_deploy.refresh import refresh_item_owners_for_source_changes

    client = RecordingRefreshClient({})
    client.cargo_rows["ObtainedFrom"] = ({"title": {"Page": "Ember Longsword"}, "SourceType": "item_use"},)

    result = refresh_item_owners_for_source_changes(
        client=client,
        changed_source_tables=("item_drops",),
        assertion="bot",
    )

    assert result.requested == ("Ember Longsword",)
    assert len(client.cargo_requests) == 1
    assert 'SourceType IN ("item_use")' in (client.cargo_requests[0][2] or "")
    assert client.null_edit_calls == [(result.requested, "bot", None)]


def test_refresh_item_owners_reparses_used_in_owners_for_crafting_changes() -> None:
    from erenshor.application.wiki_deploy.refresh import refresh_item_owners_for_source_changes

    client = RecordingRefreshClient({})
    result = refresh_item_owners_for_source_changes(
        client=client,
        changed_source_tables=("crafting_recipes",),
        assertion="bot",
    )

    assert result.requested == ("Ember Longsword",)
    assert [request[0] for request in client.cargo_requests] == ["ObtainedFrom", "UsedIn"]
    assert 'SourceType IN ("craft")' in (client.cargo_requests[0][2] or "")
    assert 'UseType IN ("craft_material")' in (client.cargo_requests[1][2] or "")
    assert client.null_edit_calls == [(result.requested, "bot", None)]


def test_refresh_item_owners_ignores_unrelated_source_changes() -> None:
    from erenshor.application.wiki_deploy.refresh import refresh_item_owners_for_source_changes

    client = RecordingRefreshClient({})
    result = refresh_item_owners_for_source_changes(
        client=client,
        changed_source_tables=("characters",),
        assertion="bot",
    )

    assert result.requested == ()
    assert result.refreshed == ()
    assert client.cargo_requests == []
    assert client.purge_calls == []


def test_refresh_embedded_pages_without_dependents_performs_no_purge() -> None:
    """When no page transcludes the dependencies, nothing is purged."""
    client = RecordingRefreshClient({})

    result = refresh_embedded_pages(
        client=client,
        dependency_titles=("Template:Unused",),
        namespaces=(0,),
        assertion="bot",
    )

    assert result.requested == ()
    assert result.refreshed == ()
    assert client.purge_calls == []
