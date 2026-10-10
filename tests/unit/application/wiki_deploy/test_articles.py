"""Tests for the guarded deployment of generated wiki articles."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki.services.storage import WikiStorage
from erenshor.application.wiki_deploy.articles import deploy_articles, plan_article_deploy
from erenshor.application.wiki_deploy.rollback import rollback_repo_pages
from erenshor.infrastructure.wiki import (
    MediaWikiAssertionError,
    MediaWikiParse,
    MediaWikiParsedLink,
    MediaWikiPermissionError,
)

if TYPE_CHECKING:
    from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest


@pytest.fixture
def storage(tmp_path: Path) -> WikiStorage:
    return WikiStorage(tmp_path / "variants" / "main" / "wiki")


def _page(storage: WikiStorage, title: str, generated: str, fetched: str | None = None, revision: int = 1) -> None:
    if fetched is not None:
        storage.save_fetched_by_title(title, [f"item:{title.lower()}"], fetched, revision)
    storage.save_generated_by_title(title, [f"item:{title.lower()}"], generated)


def _deploy(storage: WikiStorage, wiki: MediaWikiFake, tmp_path: Path):
    checkpoints: list[RepoWikiPageManifest] = []
    result = deploy_articles(
        plan_article_deploy(storage),
        client=wiki,
        storage=storage,
        repo_root=tmp_path,
        rollback_root=tmp_path / "variants" / "main" / "wiki" / "article-deploys" / "run" / "rollback",
        summary="Update game data from build 1",
        checkpoint=checkpoints.append,
    )
    return result, checkpoints


def test_writes_only_pages_still_at_their_fetched_revision(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "Alpha", "{{Item|title=Alpha|value=2}}\n", fetched="{{Item|title=Alpha|value=1}}")
    _page(storage, "Beta", "{{Item|title=Beta|value=2}}\n", fetched="{{Item|title=Beta|value=1}}")
    wiki = MediaWikiFake()
    wiki.put_page("Alpha", "{{Item|title=Alpha|value=1}}")
    wiki.put_page("Beta", "{{Item|title=Beta|value=1}}")
    wiki.put_page("Beta", "{{Item|title=Beta|value=9}}")

    result, _ = _deploy(storage, wiki, tmp_path)

    assert wiki.pages["Alpha"] == "{{Item|title=Alpha|value=2}}"
    assert wiki.pages["Beta"] == "{{Item|title=Beta|value=9}}"
    assert wiki.revisions == {"Alpha": 2, "Beta": 2}
    assert [(issue.title, issue.reason) for issue in result.conflicts] == [
        ("Beta", "changed after the fetch: live revision 2, fetched revision 1")
    ]
    assert result.failed
    alpha, beta = result.manifest.entries
    assert (alpha.title, alpha.deploy_action) == ("Alpha", "edited")
    assert (alpha.old_revision_id, alpha.new_revision_id) == (1, 2)
    assert alpha.rollback_text_source is not None
    assert (tmp_path / alpha.rollback_text_source).read_text(encoding="utf-8") == "{{Item|title=Alpha|value=1}}"
    assert (beta.title, beta.deploy_action, beta.new_revision_id) == ("Beta", None, None)
    # The fetched copy is the live page again, so a second plan has nothing to write.
    assert storage.get_metadata_by_title("Alpha").fetched_revision_id == 2
    assert plan_article_deploy(storage, page_titles=["Alpha"]).writes == ()


def test_page_deleted_after_the_fetch_is_a_conflict(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "Alpha", "{{Item|title=Alpha|value=2}}\n", fetched="{{Item|title=Alpha|value=1}}")

    result, _ = _deploy(storage, MediaWikiFake(), tmp_path)

    assert [(issue.title, issue.reason) for issue in result.conflicts] == [("Alpha", "was deleted after the fetch")]
    assert [(entry.title, entry.new_revision_id) for entry in result.manifest.entries] == [("Alpha", None)]


def test_creates_a_page_only_while_it_is_still_missing(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "New", "{{Item|title=New}}\n")
    _page(storage, "Taken", "{{Item|title=Taken}}\n")
    wiki = MediaWikiFake()
    wiki.put_page("Taken", "Editor text")

    result, _ = _deploy(storage, wiki, tmp_path)

    assert wiki.pages == {"New": "{{Item|title=New}}", "Taken": "Editor text"}
    assert wiki.revisions == {"New": 1, "Taken": 1}
    assert [(entry.title, entry.deploy_action) for entry in result.manifest.entries] == [
        ("New", "created"),
        ("Taken", None),
    ]
    assert [(issue.title, issue.reason) for issue in result.conflicts] == [
        ("Taken", "exists at revision 1 but was generated without its live text")
    ]


def test_lost_session_stops_the_run_and_keeps_the_written_pages(storage: WikiStorage, tmp_path: Path) -> None:
    for title in ("Alpha", "Beta", "Gamma"):
        _page(storage, title, f"{{{{Item|title={title}|value=2}}}}\n", fetched=f"{{{{Item|title={title}|value=1}}}}")
    wiki = MediaWikiFake()
    for title in ("Alpha", "Beta", "Gamma"):
        wiki.put_page(title, f"{{{{Item|title={title}|value=1}}}}")
    edit_page = wiki.safe_edit_page

    def fail_beta(title: str, *args, **kwargs) -> int:
        if title == "Beta":
            raise MediaWikiAssertionError("Assertion failed while safely editing page 'Beta'")
        return edit_page(title, *args, **kwargs)

    wiki.safe_edit_page = fail_beta

    result, checkpoints = _deploy(storage, wiki, tmp_path)

    assert wiki.pages == {
        "Alpha": "{{Item|title=Alpha|value=2}}",
        "Beta": "{{Item|title=Beta|value=1}}",
        "Gamma": "{{Item|title=Gamma|value=1}}",
    }
    assert wiki.revisions == {"Alpha": 2, "Beta": 1, "Gamma": 1}
    assert result.stopped == "Beta: Assertion failed while safely editing page 'Beta'"
    # Before the first write, the manifest holds every planned page with its base revision and rollback text.
    first = checkpoints[0].entries
    assert [(entry.title, entry.old_revision_id, entry.new_revision_id) for entry in first] == [
        ("Alpha", 1, None),
        ("Beta", 1, None),
        ("Gamma", 1, None),
    ]
    assert all((tmp_path / str(entry.rollback_text_source)).is_file() for entry in first)
    written = [(entry.title, entry.new_revision_id) for entry in checkpoints[-1].entries]
    assert written == [("Alpha", 2), ("Beta", None), ("Gamma", None)]


def test_refused_page_is_blocked_and_the_run_continues(storage: WikiStorage, tmp_path: Path) -> None:
    for title in ("Alpha", "Beta"):
        _page(storage, title, f"{{{{Item|title={title}|value=2}}}}\n", fetched=f"{{{{Item|title={title}|value=1}}}}")
    wiki = MediaWikiFake()
    for title in ("Alpha", "Beta"):
        wiki.put_page(title, f"{{{{Item|title={title}|value=1}}}}")
    edit_page = wiki.safe_edit_page

    def refuse_alpha(title: str, *args, **kwargs) -> int:
        if title == "Alpha":
            raise MediaWikiPermissionError("Permission denied while safely editing page 'Alpha'")
        return edit_page(title, *args, **kwargs)

    wiki.safe_edit_page = refuse_alpha

    result, _ = _deploy(storage, wiki, tmp_path)

    assert [issue.title for issue in result.blocked] == ["Alpha"]
    assert wiki.pages == {"Alpha": "{{Item|title=Alpha|value=1}}", "Beta": "{{Item|title=Beta|value=2}}"}
    assert wiki.revisions == {"Alpha": 1, "Beta": 2}
    assert result.stopped is None


def test_page_that_differs_only_by_normalization_is_not_written(storage: WikiStorage, tmp_path: Path) -> None:
    fetched = "[[Category:Zones]]\n{{Zone\n|title=Alpha\n}}\nEditor prose.  \n"
    _page(storage, "Alpha", "{{Zone\n|title=Alpha\n}}\nEditor prose.\n\n[[Category:Zones]]\n", fetched=fetched)
    wiki = MediaWikiFake()
    wiki.put_page("Alpha", fetched)

    plan = plan_article_deploy(storage)
    result, _ = _deploy(storage, wiki, tmp_path)

    assert plan.count("unchanged") == 1
    assert plan.writes == ()
    assert wiki.pages["Alpha"] == fetched.rstrip()
    assert wiki.revisions["Alpha"] == 1
    assert not result.failed


def test_rollback_restores_only_the_written_articles(storage: WikiStorage, tmp_path: Path) -> None:
    _page(storage, "Alpha", "{{Item|title=Alpha|value=2}}\n", fetched="{{Item|title=Alpha|value=1}}")
    _page(storage, "Beta", "{{Item|title=Beta|value=2}}\n", fetched="{{Item|title=Beta|value=1}}")
    wiki = MediaWikiFake()
    wiki.put_page("Alpha", "{{Item|title=Alpha|value=1}}")
    wiki.put_page("Beta", "{{Item|title=Beta|value=1}}")
    wiki.put_page("Beta", "Editor text")
    result, _ = _deploy(storage, wiki, tmp_path)

    rollback = rollback_repo_pages(
        manifest=result.manifest, repo_root=tmp_path, client=wiki, summary="Roll back", assertion="bot"
    )

    assert [entry.title for entry in rollback.entries] == ["Alpha"]
    assert wiki.pages["Alpha"] == "{{Item|title=Alpha|value=1}}"
    assert wiki.revisions["Alpha"] == 3
    assert wiki.pages["Beta"] == "Editor text"
    assert wiki.revisions["Beta"] == 2


def _parse(
    html: str = "<p></p>",
    templates: tuple[tuple[str, bool], ...] = (),
    categories: tuple[tuple[str, bool], ...] = (),
) -> MediaWikiParse:
    return MediaWikiParse(
        html=html,
        templates=tuple(MediaWikiParsedLink(title, exists) for title, exists in templates),
        categories=tuple(MediaWikiParsedLink(title, exists) for title, exists in categories),
    )


def _clean_pages(storage: WikiStorage, *titles: str) -> MediaWikiFake:
    for title in titles:
        _page(storage, title, f"{{{{Item|title={title}|value=2}}}}\n", fetched=f"{{{{Item|title={title}|value=1}}}}")
    wiki = MediaWikiFake()
    for title in titles:
        wiki.put_page(title, f"{{{{Item|title={title}|value=1}}}}")
    return wiki


def test_text_with_a_script_error_or_a_missing_template_is_blocked(storage: WikiStorage, tmp_path: Path) -> None:
    wiki = _clean_pages(storage, "Alpha", "Beta", "Gamma")
    wiki.parse_overrides[("Alpha", None)] = _parse(
        html='<strong class="error"><span class="scribunto-error mw-x">Lua error</span></strong>'
    )
    wiki.parse_overrides[("Beta", None)] = _parse(templates=(("Template:Item", True), ("Template:Gone", False)))

    result, _ = _deploy(storage, wiki, tmp_path)

    assert [(issue.title, issue.reason) for issue in result.blocked] == [
        ("Alpha", "script error"),
        ("Beta", "missing template Template:Gone"),
    ]
    assert wiki.revisions == {"Alpha": 1, "Beta": 1, "Gamma": 2}
    assert wiki.pages["Gamma"] == "{{Item|title=Gamma|value=2}}"


def test_new_category_without_a_page_blocks_the_page(storage: WikiStorage, tmp_path: Path) -> None:
    wiki = _clean_pages(storage, "Elite", "Editor")
    wiki.parse_overrides[("Elite", None)] = _parse(
        categories=(("Category:Characters", True), ("Category:Elites", False))
    )
    # The live page is already in the red category, so the write does not make it worse.
    wiki.parse_overrides[("Editor", None)] = _parse(categories=(("Category:Old Zone", False),))
    wiki.page_categories["Editor"] = frozenset({"Category:Old Zone"})

    result, _ = _deploy(storage, wiki, tmp_path)

    assert [(issue.title, issue.reason) for issue in result.blocked] == [
        ("Elite", "category without a page: Category:Elites")
    ]
    assert wiki.revisions == {"Elite": 1, "Editor": 2}
    assert wiki.pages["Editor"] == "{{Item|title=Editor|value=2}}"


def test_new_link_tracking_category_blocks_the_page(storage: WikiStorage, tmp_path: Path) -> None:
    unresolved = "Category:Pages with unresolved Erenshor links"
    wiki = _clean_pages(storage, "Alpha", "Beta")
    wiki.parse_overrides[("Alpha", None)] = _parse(categories=((unresolved, True),))
    wiki.parse_overrides[("Beta", None)] = _parse(categories=((unresolved, True),))
    wiki.page_categories["Beta"] = frozenset({unresolved})

    result, _ = _deploy(storage, wiki, tmp_path)

    assert [(issue.title, issue.reason) for issue in result.blocked] == [
        ("Alpha", f"new link tracking category: {unresolved}")
    ]
    assert wiki.revisions == {"Alpha": 1, "Beta": 2}
    assert wiki.pages["Beta"] == "{{Item|title=Beta|value=2}}"
