"""Tests for dependency-derived MediaWiki null edits."""

from __future__ import annotations

from erenshor.application.wiki_deploy.null_edit import null_edit_embedded_pages
from erenshor.infrastructure.wiki import MediaWikiPageRevision


class RecordingNullEditClient:
    def __init__(self) -> None:
        self.embeddedin_requests: list[tuple[str, tuple[int, ...], str, str | None]] = []
        self.pages: dict[str, str | None] = {
            "Ember Longsword": "{{Item|stablekey=item:ember_longsword}}\n",
            "Abyssal Plate": "{{Item|stablekey=item:abyssal_plate}}\n",
        }
        self.safe_edits: list[tuple[str, str, MediaWikiPageRevision, str, str, str | None]] = []

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: tuple[int, ...],
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        self.embeddedin_requests.append((title, namespaces, assertion or "", assert_user))
        if title == "Template:Item":
            return ("Ember Longsword", "Abyssal Plate")
        if title == "Module:Erenshor/Item":
            return ("Ember Longsword",)
        return ()

    def get_pages(self, titles: list[str]) -> dict[str, str | None]:
        return {title: self.pages.get(title) for title in titles}

    def get_page_revision_metadata(
        self,
        title: str,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> MediaWikiPageRevision | None:
        return MediaWikiPageRevision(
            title=title,
            page_id=10,
            revision_id=20,
            timestamp="2026-06-04T12:00:00Z",
            start_timestamp="2026-06-04T12:01:00Z",
        )

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str,
        assertion: str,
        assert_user: str | None,
    ) -> int:
        self.safe_edits.append((title, content, base_revision, summary, assertion, assert_user))
        return base_revision.revision_id + 1


def test_null_edit_embedded_pages_uses_dependency_discovery_and_safe_edits_content() -> None:
    """Null edits are derived from embeddedin dependencies and edit unchanged page text."""
    client = RecordingNullEditClient()

    result = null_edit_embedded_pages(
        client=client,
        dependency_titles=("Template:Item", "Module:Erenshor/Item"),
        namespaces=(0,),
        summary="Refresh pages after wiki data deploy",
        assertion="bot",
        assert_user="ErenshorBot",
    )

    assert client.embeddedin_requests == [
        ("Template:Item", (0,), "bot", "ErenshorBot"),
        ("Module:Erenshor/Item", (0,), "bot", "ErenshorBot"),
    ]
    assert [entry.title for entry in result.entries] == ["Abyssal Plate", "Ember Longsword"]
    assert [entry.new_revision_id for entry in result.entries] == [21, 21]
    assert client.safe_edits == [
        (
            "Abyssal Plate",
            "{{Item|stablekey=item:abyssal_plate}}\n",
            MediaWikiPageRevision(
                title="Abyssal Plate",
                page_id=10,
                revision_id=20,
                timestamp="2026-06-04T12:00:00Z",
                start_timestamp="2026-06-04T12:01:00Z",
            ),
            "Refresh pages after wiki data deploy",
            "bot",
            "ErenshorBot",
        ),
        (
            "Ember Longsword",
            "{{Item|stablekey=item:ember_longsword}}\n",
            MediaWikiPageRevision(
                title="Ember Longsword",
                page_id=10,
                revision_id=20,
                timestamp="2026-06-04T12:00:00Z",
                start_timestamp="2026-06-04T12:01:00Z",
            ),
            "Refresh pages after wiki data deploy",
            "bot",
            "ErenshorBot",
        ),
    ]
