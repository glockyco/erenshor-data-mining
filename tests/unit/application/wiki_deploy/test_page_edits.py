"""Planning reviewed one-time edits of live pages."""

from pathlib import Path

import pytest
from tests.fakes.mediawiki import MediaWikiFake

from erenshor.application.wiki_deploy.page_edits import (
    PageEditError,
    PageEditRequest,
    TextReplacement,
    load_page_edit_requests,
    parse_page_edit_requests,
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


def test_captured_edit_bytes_do_not_reread_the_source(tmp_path: Path) -> None:
    path = tmp_path / "edits.toml"
    captured = (
        b'[[pages]]\ntitle = "Ancient Horror"\nsummary = "Reviewed"\n'
        b'[[pages.replace]]\nold = "Old prose"\nnew = "Approved prose"\n'
    )
    path.write_bytes(captured)
    path.write_bytes(captured.replace(b"Approved prose", b"Unreviewed prose"))

    [request] = parse_page_edit_requests(captured, source=str(path))

    assert request.replacements == (TextReplacement("Old prose", "Approved prose"),)
    assert load_page_edit_requests(path)[0].replacements == (TextReplacement("Old prose", "Unreviewed prose"),)


def test_captured_edit_validation_names_its_source() -> None:
    with pytest.raises(PageEditError, match=r"reviewed-edits\.toml lists no"):
        parse_page_edit_requests(b"pages = []", source="reviewed-edits.toml")


@pytest.mark.parametrize("content_model", ["wikitext", "Scribunto", "sanitized-css"])
def test_one_time_edits_preserve_the_live_content_model(content_model: str) -> None:
    wiki = MediaWikiFake()
    title = "User:Editor/Reviewed source"
    wiki.put_page(title, "old editor text", content_model=content_model)
    request = PageEditRequest(title, "Reviewed replacement", (TextReplacement("old", "new"),))

    [edit] = plan_page_edits([request], wiki)

    assert edit.content_model == content_model
    assert edit.original == "old editor text"
    assert edit.content == "new editor text"


@pytest.mark.parametrize("content_model", [None, "json"])
def test_one_time_edits_refuse_unknown_content_model(content_model: str | None) -> None:
    wiki = MediaWikiFake()
    title = "User:Editor/Reviewed source"
    wiki.put_page(title, "old editor text", content_model=content_model)
    if content_model is None:
        wiki.content_models.pop(title)
    request = PageEditRequest(title, "Reviewed replacement", (TextReplacement("old", "new"),))

    with pytest.raises(PageEditError, match="unsupported or missing content model"):
        plan_page_edits([request], wiki)
