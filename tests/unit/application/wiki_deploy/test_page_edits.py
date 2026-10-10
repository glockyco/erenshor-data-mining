"""Planning reviewed one-time edits of live pages."""

from pathlib import Path

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_deploy.page_edits import (
    PageEditError,
    PageEditRequest,
    TextReplacement,
    load_page_edit_requests,
    plan_page_edits,
    render_problems,
)


def _request(*replacements: tuple[str, str]) -> PageEditRequest:
    return PageEditRequest(
        "Ancient Horror", "Replace the legacy blocks", tuple(TextReplacement(old, new) for old, new in replacements)
    )


def test_replacements_apply_in_order_to_the_live_text() -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Ancient Horror", "[[Category:Treasure Hunting]]\n{{Enemy}}\n{{Enemy Stats}}")
    wiki.put_page("Category:Treasure Hunting", "Treasure hunting pages")

    [edit] = plan_page_edits([_request(("{{Enemy}}\n", ""), ("{{Enemy Stats}}", ""))], wiki)

    assert edit.content == "[[Category:Treasure Hunting]]\n"
    assert edit.original == "[[Category:Treasure Hunting]]\n{{Enemy}}\n{{Enemy Stats}}"
    assert edit.revision.revision_id == 1
    assert edit.summary == "Replace the legacy blocks"


@pytest.mark.parametrize("text", ["{{Enemy Stats}}", "{{Enemy}}{{Enemy}}"])
def test_an_old_text_that_is_not_on_the_page_exactly_once_fails(text: str) -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Ancient Horror", text)
    with pytest.raises(PageEditError, match="Ancient Horror holds the text"):
        plan_page_edits([_request(("{{Enemy}}", ""))], wiki)


def test_a_missing_page_fails() -> None:
    with pytest.raises(PageEditError, match="Ancient Horror does not exist"):
        plan_page_edits([_request(("{{Enemy}}", ""))], MediaWikiFake())


def test_only_a_problem_that_the_live_page_does_not_have_blocks() -> None:
    wiki = MediaWikiFake()
    wiki.put_page("Ancient Horror", "{{Enemy}}[[Category:Missing]]")
    [kept] = plan_page_edits([_request(("{{Enemy}}", "text"))], wiki)
    assert render_problems(kept, wiki) == ()

    wiki = MediaWikiFake()
    wiki.put_page("Ancient Horror", "{{Enemy}}")
    [added] = plan_page_edits([_request(("{{Enemy}}", "[[Category:Missing]]"))], wiki)
    assert render_problems(added, wiki) == ("category without a page: Category:Missing",)


def test_an_edit_file_without_a_changed_text_fails(tmp_path: Path) -> None:
    path = tmp_path / "edits.toml"
    path.write_text(
        '[[pages]]\ntitle = "Ancient Horror"\nsummary = "s"\n[[pages.replace]]\nold = "a"\nnew = "a"\n',
        encoding="utf-8",
    )

    with pytest.raises(PageEditError, match="without a changed text"):
        load_page_edit_requests(path)
