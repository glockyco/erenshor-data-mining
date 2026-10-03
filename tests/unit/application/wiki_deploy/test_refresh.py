"""Tests for dependency-derived refresh of transcluding pages."""

from __future__ import annotations

from collections.abc import Sequence

from erenshor.application.wiki_deploy.refresh import refresh_embedded_pages


class RecordingRefreshClient:
    def __init__(self, embeddedin: dict[str, tuple[str, ...]]) -> None:
        self.embeddedin = embeddedin
        self.embeddedin_requests: list[tuple[str, tuple[int, ...], str, str | None]] = []
        self.purge_calls: list[tuple[tuple[str, ...], bool, str, str | None]] = []

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        self.embeddedin_requests.append((title, tuple(namespaces), assertion or "", assert_user))
        return self.embeddedin.get(title, ())

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
