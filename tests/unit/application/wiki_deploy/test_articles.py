"""Tests for the guarded deployment of generated wiki articles."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_deploy.articles import deploy_articles, plan_article_deploy
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import (
    MediaWikiAssertionError,
    MediaWikiPageRevision,
    MediaWikiPageSnapshot,
    MediaWikiPermissionError,
)

if TYPE_CHECKING:
    from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest

START = "2026-10-03T12:00:00Z"


class FakeWiki:
    """A live wiki: each page has a revision and saved text."""

    def __init__(self, pages: dict[str, tuple[int, str]]) -> None:
        self.pages = dict(pages)
        self.next_revision = 1000
        self.writes: list[tuple[str, str, int | None, str | None]] = []
        self.failures: dict[str, Exception] = {}

    def _revision(self, title: str) -> MediaWikiPageRevision | None:
        if title not in self.pages:
            return None
        return MediaWikiPageRevision(title, 7, self.pages[title][0], "2026-10-01T00:00:00Z", START)

    def get_page_snapshots(
        self, titles: Sequence[str], assertion: str | None = None, assert_user: str | None = None
    ) -> dict[str, MediaWikiPageSnapshot]:
        return {
            title: MediaWikiPageSnapshot(
                title=title,
                source_text=self.pages[title][1] if title in self.pages else None,
                revision=self._revision(title),
                start_timestamp=START,
            )
            for title in titles
        }

    def get_page_revision_metadata(
        self, title: str, assertion: str | None = None, assert_user: str | None = None
    ) -> MediaWikiPageRevision | None:
        return self._revision(title)

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: str = "bot",
        assert_user: str | None = None,
    ) -> int:
        return self._save(title, content, base_revision.revision_id, summary)

    def safe_create_page(
        self,
        title: str,
        content: str,
        start_timestamp: str,
        summary: str | None = None,
        minor: bool | None = None,
        bot: bool = True,
        assertion: str = "bot",
        assert_user: str | None = None,
    ) -> int:
        return self._save(title, content, None, summary)

    def _save(self, title: str, content: str, base_revision_id: int | None, summary: str | None) -> int:
        if title in self.failures:
            raise self.failures[title]
        self.writes.append((title, content, base_revision_id, summary))
        self.next_revision += 1
        self.pages[title] = (self.next_revision, content.rstrip())
        return self.next_revision


@pytest.fixture
def storage(tmp_path: Path) -> WikiStorage:
    return WikiStorage(tmp_path / "variants" / "main" / "wiki")


def _page(storage: WikiStorage, title: str, generated: str, fetched: str | None = None, revision: int = 10) -> None:
    if fetched is not None:
        storage.save_fetched_by_title(title, [f"item:{title.lower()}"], fetched, [title], revision)
    storage.save_generated_by_title(title, [f"item:{title.lower()}"], generated)


def _deploy(storage: WikiStorage, wiki: FakeWiki, tmp_path: Path):
    checkpoints: list[RepoWikiPageManifest] = []
    result = deploy_articles(
        plan_article_deploy(storage),
        client=wiki,
        storage=storage,
        repo_root=tmp_path,
        rollback_root=tmp_path / "variants" / "main" / "wiki" / "article-deploys" / "run" / "rollback",
        summary="Update game data from build 1",
        checkpoint=checkpoints.append,
        sleep=lambda _: None,
    )
    return result, checkpoints


def test_writes_only_pages_still_at_their_fetched_revision(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "Alpha", "{{Item|title=Alpha|value=2}}\n", fetched="{{Item|title=Alpha|value=1}}")
    _page(storage, "Beta", "{{Item|title=Beta|value=2}}\n", fetched="{{Item|title=Beta|value=1}}")
    wiki = FakeWiki({"Alpha": (10, "{{Item|title=Alpha|value=1}}"), "Beta": (11, "{{Item|title=Beta|value=9}}")})

    result, _ = _deploy(storage, wiki, tmp_path)

    assert wiki.writes == [("Alpha", "{{Item|title=Alpha|value=2}}\n", 10, "Update game data from build 1")]
    assert [(issue.title, issue.reason) for issue in result.conflicts] == [
        ("Beta", "changed after the fetch: live revision 11, fetched revision 10")
    ]
    assert result.failed
    [entry] = result.manifest.entries
    assert (entry.title, entry.deploy_action) == ("Alpha", "edited")
    assert (entry.old_revision_id, entry.new_revision_id) == (10, 1001)
    assert entry.rollback_text_source is not None
    assert (tmp_path / entry.rollback_text_source).read_text(encoding="utf-8") == "{{Item|title=Alpha|value=1}}"
    # The fetched copy is the live page again, so a second plan has nothing to write.
    assert storage.get_metadata_by_title("Alpha").fetched_revision_id == 1001
    assert plan_article_deploy(storage, page_titles=["Alpha"]).writes == ()


def test_page_deleted_after_the_fetch_is_a_conflict(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "Alpha", "{{Item|title=Alpha|value=2}}\n", fetched="{{Item|title=Alpha|value=1}}")

    result, _ = _deploy(storage, FakeWiki({}), tmp_path)

    assert [(issue.title, issue.reason) for issue in result.conflicts] == [("Alpha", "was deleted after the fetch")]
    assert result.manifest.entries == ()


def test_creates_a_page_only_while_it_is_still_missing(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "New", "{{Item|title=New}}\n")
    _page(storage, "Taken", "{{Item|title=Taken}}\n")
    wiki = FakeWiki({"Taken": (12, "Editor text")})

    result, _ = _deploy(storage, wiki, tmp_path)

    assert [(title, base) for title, _, base, _ in wiki.writes] == [("New", None)]
    assert [entry.deploy_action for entry in result.manifest.entries] == ["created"]
    assert [(issue.title, issue.reason) for issue in result.conflicts] == [
        ("Taken", "exists at revision 12 but was generated without its live text")
    ]


def test_lost_session_stops_the_run_and_keeps_the_written_pages(storage: WikiStorage, tmp_path: Path) -> None:
    for title in ("Alpha", "Beta", "Gamma"):
        _page(storage, title, f"{{{{Item|title={title}|value=2}}}}\n", fetched=f"{{{{Item|title={title}|value=1}}}}")
    wiki = FakeWiki({title: (10, f"{{{{Item|title={title}|value=1}}}}") for title in ("Alpha", "Beta", "Gamma")})
    wiki.failures["Beta"] = MediaWikiAssertionError("Assertion failed while safely editing page 'Beta'")

    result, checkpoints = _deploy(storage, wiki, tmp_path)

    assert [title for title, *_ in wiki.writes] == ["Alpha"]
    assert result.stopped == "Beta: Assertion failed while safely editing page 'Beta'"
    assert [entry.title for entry in result.manifest.entries] == ["Alpha"]
    assert [entry.title for entry in checkpoints[-1].entries] == ["Alpha"]


def test_refused_page_is_blocked_and_the_run_continues(storage: WikiStorage, tmp_path: Path) -> None:
    for title in ("Alpha", "Beta"):
        _page(storage, title, f"{{{{Item|title={title}|value=2}}}}\n", fetched=f"{{{{Item|title={title}|value=1}}}}")
    wiki = FakeWiki({title: (10, f"{{{{Item|title={title}|value=1}}}}") for title in ("Alpha", "Beta")})
    wiki.failures["Alpha"] = MediaWikiPermissionError("Permission denied while safely editing page 'Alpha'")

    result, _ = _deploy(storage, wiki, tmp_path)

    assert [issue.title for issue in result.blocked] == ["Alpha"]
    assert [title for title, *_ in wiki.writes] == ["Beta"]
    assert result.stopped is None


def test_page_that_differs_only_by_normalization_is_not_written(storage: WikiStorage, tmp_path: Path) -> None:
    fetched = "[[Category:Zones]]\n{{Zone\n|title=Alpha\n}}\nEditor prose.  \n"
    _page(storage, "Alpha", "{{Zone\n|title=Alpha\n}}\nEditor prose.\n\n[[Category:Zones]]\n", fetched=fetched)
    wiki = FakeWiki({"Alpha": (10, fetched)})

    plan = plan_article_deploy(storage)
    result, _ = _deploy(storage, wiki, tmp_path)

    assert plan.count("unchanged") == 1
    assert plan.writes == ()
    assert wiki.writes == []
    assert not result.failed


def test_rollback_restores_a_deployed_article(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "Alpha", "{{Item|title=Alpha|value=2}}\n", fetched="{{Item|title=Alpha|value=1}}")
    wiki = FakeWiki({"Alpha": (10, "{{Item|title=Alpha|value=1}}")})
    result, _ = _deploy(storage, wiki, tmp_path)

    rollback = rollback_repo_pages(
        manifest=result.manifest, repo_root=tmp_path, client=wiki, summary="Roll back", assertion="bot"
    )

    assert [entry.title for entry in rollback.entries] == ["Alpha"]
    assert wiki.writes[-1] == ("Alpha", "{{Item|title=Alpha|value=1}}", 1001, "Roll back")
    assert wiki.pages["Alpha"][1] == "{{Item|title=Alpha|value=1}}"
