"""Tests for dependency-derived refresh of transcluding pages."""

from __future__ import annotations

from tests.fakes.mediawiki import MediaWikiFake, PurgeRequest

from erenshor.application.wiki_deploy.refresh import refresh_embedded_pages


def test_refresh_embedded_pages_purges_deduplicated_dependents_with_forced_link_update() -> None:
    """Dependents discovered from every dependency are purged once with a forced link update."""
    client = MediaWikiFake(
        embedded_in={
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
    assert client.purged == [
        PurgeRequest(("Abyssal Plate", "Ember Longsword", "Frost Dagger"), True, "bot", "ErenshorBot")
    ]


def test_refresh_embedded_pages_without_dependents_performs_no_purge() -> None:
    """When no page transcludes the dependencies, nothing is purged."""
    client = MediaWikiFake()

    result = refresh_embedded_pages(
        client=client,
        dependency_titles=("Template:Unused",),
        namespaces=(0,),
        assertion="bot",
    )

    assert result.requested == ()
    assert result.refreshed == ()
    assert client.purged == []
