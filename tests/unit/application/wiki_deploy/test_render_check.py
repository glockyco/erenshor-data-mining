"""Observable dependency and sandbox-render safety checks for repository pages."""

from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.wiki_deploy.dependencies import literal_dependencies
from erenshor.application.wiki_deploy.manifest import build_repo_page_manifest
from erenshor.application.wiki_deploy.pages import (
    deploy_repo_pages,
    prepare_repo_page_checks,
    read_repo_page_sources,
    render_repo_page_checks,
)
from erenshor.application.wiki_deploy.render_check import RenderCheckError, check_render, select_render_pages
from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry
from erenshor.infrastructure.wiki.client import (
    MediaWikiPageRevision,
    MediaWikiPageSnapshot,
    MediaWikiParse,
    MediaWikiParsedLink,
)


def source(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class Wiki:
    edit_account = "Bot"

    def __init__(self, pages: dict[str, str | None], users: dict[str, tuple[str, ...]] | None = None) -> None:
        self.pages = pages
        self.users = users or {}
        self.writes: list[str] = []
        self.parsed: list[tuple[str, str | None]] = []
        self.sandbox_models: list[str | None] = []
        self.sandbox_html = "<p>new</p>"
        self.live_categories: tuple[MediaWikiParsedLink, ...] = ()
        self.sandbox_categories: tuple[MediaWikiParsedLink, ...] = ()
        self.sandbox_templates: tuple[MediaWikiParsedLink, ...] = ()

    def get_page_snapshots(
        self, titles: list[str], assertion: str | None = None, assert_user: str | None = None
    ) -> dict[str, MediaWikiPageSnapshot]:
        return {
            title: MediaWikiPageSnapshot(
                title,
                self.pages.get(title),
                MediaWikiPageRevision(title, 1, 10, "2026-01-01", "2026-01-02", "Bot")
                if self.pages.get(title) is not None
                else None,
                "2026-01-02",
            )
            for title in titles
        }

    def get_pages(self, titles: list[str]) -> dict[str, str | None]:
        return {title: self.pages.get(title) for title in titles}

    def get_embeddedin_pages(self, title: str, namespaces: tuple[int, ...] = (0,)) -> tuple[str, ...]:
        assert namespaces == (0,)
        return self.users.get(title, ())

    def parse_wikitext(
        self,
        title: str,
        text: str,
        *,
        sandbox_title: str | None = None,
        sandbox_text: str | None = None,
        sandbox_content_model: str | None = None,
    ) -> MediaWikiParse:
        self.parsed.append((title, sandbox_title))
        if sandbox_title is not None:
            self.sandbox_models.append(sandbox_content_model)
        return MediaWikiParse(
            self.sandbox_html if sandbox_title else "<p>old</p>",
            self.sandbox_templates if sandbox_title else (),
            self.sandbox_categories if sandbox_title else self.live_categories,
        )

    def safe_create_page(
        self, title: str, content: str, start_timestamp: str, summary: str, assertion: str, assert_user: str | None
    ) -> int:
        self.writes.append(title)
        self.pages[title] = content
        return 11

    def safe_edit_page(
        self,
        title: str,
        content: str,
        base_revision: MediaWikiPageRevision,
        summary: str,
        assertion: str,
        assert_user: str | None,
    ) -> int:
        self.writes.append(title)
        self.pages[title] = content
        return 11


def deploy(root: Path, wiki: Wiki, **options: object) -> None:
    manifest = build_repo_page_manifest(root, variant="main", include_templates=True, include_generated_data=True)
    deploy_repo_pages(
        manifest=manifest,
        repo_root=root,
        client=wiki,
        assertion="bot",
        summary="test",
        include_templates=True,
        include_generated_data=True,
        **options,
    )


def test_missing_data_module_blocks_template_and_names_both(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/MapLink.wiki", "{{#invoke:Erenshor/Zone|map}}")
    wiki = Wiki({"Module:Erenshor/Zone": "local data = mw.loadData('Module:Erenshor/Data/Zones')"})
    with pytest.raises(ValueError, match="Template:MapLink needs missing page Module:Erenshor/Data/Zones"):
        deploy(tmp_path, wiki)
    assert wiki.writes == []


def test_module_and_new_data_module_pass_in_one_run(tmp_path: Path) -> None:
    source(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Zones.lua", "return {}")
    source(tmp_path, "wiki/modules/Erenshor/Zone.lua", "return mw.loadData('Module:Erenshor/Data/Zones')")
    wiki = Wiki({})
    deploy(tmp_path, wiki)
    assert wiki.writes == ["Module:Erenshor/Data/Zones", "Module:Erenshor/Zone"]


def test_modules_write_in_dependency_order_within_stage(tmp_path: Path) -> None:
    source(tmp_path, "wiki/modules/Erenshor/A.lua", "return require('Module:Erenshor/Z')")
    source(tmp_path, "wiki/modules/Erenshor/Z.lua", "return {}")
    wiki = Wiki({})
    deploy(tmp_path, wiki)
    assert wiki.writes == ["Module:Erenshor/Z", "Module:Erenshor/A"]


def test_new_script_error_blocks_write_and_names_user(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item.wiki", "new")
    wiki = Wiki({"Template:Item": "old", "Example": "{{Item}}"}, {"Template:Item": ("Example",)})
    wiki.sandbox_html = '<strong class="scribunto-error">Lua error</strong>'
    with pytest.raises(RenderCheckError, match="Template:Item blocked on Example: script error"):
        deploy(tmp_path, wiki, render_check=True)
    assert wiki.writes == []


def test_new_missing_template_blocks_write(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item.wiki", "new")
    wiki = Wiki({"Template:Item": "old", "Example": "{{Item}}"}, {"Template:Item": ("Example",)})
    wiki.sandbox_templates = (MediaWikiParsedLink("Template:Missing", False),)
    with pytest.raises(RenderCheckError, match="Template:Item blocked on Example: missing template Template:Missing"):
        deploy(tmp_path, wiki, render_check=True)
    assert wiki.writes == []


def test_visible_change_reports_removed_added_lines(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item.wiki", "new")
    wiki = Wiki({"Template:Item": "old", "Example": "{{Item}}"}, {"Template:Item": ("Example",)})
    reports = []
    deploy(tmp_path, wiki, render_check=True, report_render=reports.append)
    [change] = reports[0].differences
    assert (change.title, change.removed, change.added) == ("Example", ("old",), ("new",))
    assert wiki.writes == ["Template:Item"]


def test_category_change_reports_removed_added_categories() -> None:
    wiki = Wiki({"Example": "{{Item}}"}, {"Template:Item": ("Example",)})
    wiki.sandbox_html = "<p>old</p>"
    wiki.live_categories = (MediaWikiParsedLink("Category:Old", True),)
    wiki.sandbox_categories = (MediaWikiParsedLink("Category:New", True),)
    report = check_render(wiki, "Template:Item", "new", content_model="wikitext", catalog={}, live_cache={})
    [change] = report.differences
    assert change.removed == ("Category:Old",)
    assert change.added == ("Category:New",)


def test_hidden_html_difference_is_not_reported() -> None:
    wiki = Wiki({"Example": "{{Item}}"}, {"Template:Item": ("Example",)})
    wiki.sandbox_html = '<p>old</p><span style="display: none">internal change</span>'
    report = check_render(wiki, "Template:Item", "new", content_model="wikitext", catalog={}, live_cache={})
    assert report.differences == ()


def test_default_selection_includes_unique_aura_kind() -> None:
    texts = {f"Page {i:03}": "{{Ability|kind=Spell|stablekey=spell:fire}}" for i in range(800)}
    texts["Page 799"] = "{{Ability|kind=Aura|stablekey=spell:fire}}"
    catalog = {"spell:fire": LinkCatalogEntry("spell:fire", "ability", "spell", "Fire", "Fire", None)}
    assert "Page 799" in select_render_pages(texts, catalog)


def test_full_render_check_parses_every_user_and_no_users_are_reported() -> None:
    wiki = Wiki({"A": "{{Item}}", "B": "{{Item}}"}, {"Template:Item": ("A", "B")})
    full = check_render(wiki, "Template:Item", "new", content_model="wikitext", catalog={}, live_cache={}, full=True)
    assert full.checked == ("A", "B")
    assert wiki.parsed == [("A", None), ("A", "Template:Item"), ("B", None), ("B", "Template:Item")]
    empty = check_render(wiki, "Template:New", "new", content_model="wikitext", catalog={}, live_cache={})
    assert empty.users == 0 and empty.checked == ()


def test_dry_run_reuses_live_parse_for_shared_user(tmp_path: Path) -> None:
    source(tmp_path, "wiki/modules/Erenshor/A.lua", "return {}")
    source(tmp_path, "wiki/modules/Erenshor/B.lua", "return {}")
    wiki = Wiki(
        {"Example": "{{A}}{{B}}"},
        {
            "Module:Erenshor/A": ("Example",),
            "Module:Erenshor/B": ("Example",),
        },
    )
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    sources = read_repo_page_sources(manifest, tmp_path)
    snapshots = wiki.get_page_snapshots([entry.title for entry in manifest.entries])
    ordered = prepare_repo_page_checks(manifest, sources, snapshots, wiki)
    render_repo_page_checks(ordered, sources, snapshots, wiki, catalog={}, dry_run=True)
    assert wiki.parsed == [
        ("Example", None),
        ("Example", "Module:Erenshor/A"),
        ("Example", "Module:Erenshor/B"),
    ]


def test_dry_run_provisional_for_same_run_dependency(tmp_path: Path) -> None:
    source(tmp_path, "wiki/modules/Erenshor/Z.lua", "return {}")
    source(tmp_path, "wiki/templates/Item.wiki", "{{#invoke:Erenshor/Z|main}}")
    wiki = Wiki({"Template:Item": "old", "Example": "{{Item}}"}, {"Template:Item": ("Example",)})
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)
    sources = read_repo_page_sources(manifest, tmp_path)
    snapshots = wiki.get_page_snapshots([entry.title for entry in manifest.entries])
    ordered = prepare_repo_page_checks(manifest, sources, snapshots, wiki)
    reports = []
    render_repo_page_checks(ordered, sources, snapshots, wiki, catalog={}, dry_run=True, report=reports.append)
    assert next(report for report in reports if report.title == "Template:Item").provisional
    assert wiki.writes == []


def test_dry_run_reports_a_script_error_of_a_page_whose_dependency_the_run_writes(tmp_path: Path) -> None:
    source(tmp_path, "wiki/modules/Erenshor/Icon.lua", "return {}")
    source(tmp_path, "wiki/modules/Erenshor/Link.lua", "return require('Module:Erenshor/Icon')")
    wiki = Wiki({"Module:Erenshor/Link": "return {}", "Example": "{{Item}}"}, {"Module:Erenshor/Link": ("Example",)})
    # The sandbox cannot load the new module that the deploy writes first.
    wiki.sandbox_html = '<strong class="scribunto-error">Lua error: module not found</strong>'
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)
    sources = read_repo_page_sources(manifest, tmp_path)
    snapshots = wiki.get_page_snapshots([entry.title for entry in manifest.entries])
    ordered = prepare_repo_page_checks(manifest, sources, snapshots, wiki)
    reports = []

    render_repo_page_checks(ordered, sources, snapshots, wiki, catalog={}, dry_run=True, report=reports.append)

    link = next(report for report in reports if report.title == "Module:Erenshor/Link")
    assert link.problems == ("Example: script error",)


def test_a_template_that_transcludes_a_new_template_of_the_run_comes_after_it(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Gear/Slot.wiki", "{{Icon|Branch.png|kind=item|size=60}}")
    source(
        tmp_path,
        "wiki/templates/Icon.wiki",
        "<includeonly>frame</includeonly><noinclude><pre>{{Icon|x}}</pre></noinclude>",
    )
    wiki = Wiki({})

    deploy(tmp_path, wiki)

    # By title alone Gear/Slot comes first and shows a missing template until Icon is written.
    assert wiki.writes == ["Template:Icon", "Template:Gear/Slot"]


def test_documentation_examples_that_transclude_each_other_do_not_stop_the_deploy(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item/Header.wiki", "header<noinclude>{{SparkleIcon|icon=x}}</noinclude>")
    source(tmp_path, "wiki/templates/SparkleIcon.wiki", "sparkle<noinclude>{{Item/Header}}</noinclude>")
    wiki = Wiki({})

    deploy(tmp_path, wiki)

    assert sorted(wiki.writes) == ["Template:Item/Header", "Template:SparkleIcon"]


STYLESHEET_TEMPLATE = '<templatestyles src="Template:Item/styles.css" />{{#if:{{{name|}}}|{{{name}}}}}'


def test_stylesheet_writes_before_the_template_that_loads_it(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item.wiki", STYLESHEET_TEMPLATE)
    source(tmp_path, "wiki/templates/Item/styles.css", ".pi-image { color: red; }")
    wiki = Wiki({})
    deploy(tmp_path, wiki)
    # By title alone the template would come first and load a missing stylesheet.
    assert wiki.writes == ["Template:Item/styles.css", "Template:Item"]


def test_template_with_a_missing_stylesheet_stops_the_deploy(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item.wiki", STYLESHEET_TEMPLATE)
    wiki = Wiki({})
    with pytest.raises(ValueError, match=r"Template:Item needs missing page Template:Item/styles\.css"):
        deploy(tmp_path, wiki)
    assert wiki.writes == []


def test_stylesheet_renders_its_users_as_sanitized_css(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item/styles.css", ".pi-image { color: blue; }")
    wiki = Wiki(
        {"Template:Item/styles.css": ".pi-image { color: red; }", "Example": "{{Item}}"},
        {"Template:Item/styles.css": ("Example",)},
    )
    wiki.sandbox_html = "<p>old</p>"
    deploy(tmp_path, wiki, render_check=True)
    assert wiki.sandbox_models == ["sanitized-css"]
    assert wiki.writes == ["Template:Item/styles.css"]


def test_dry_run_accepts_a_stylesheet_that_the_same_deploy_creates(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item.wiki", STYLESHEET_TEMPLATE)
    source(tmp_path, "wiki/templates/Item/styles.css", ".pi-image { color: red; }")
    wiki = Wiki({"Template:Item": "old", "Example": "{{Item}}"}, {"Template:Item": ("Example",)})
    # Live, the stylesheet does not exist yet, so the sandboxed template finds it missing.
    wiki.sandbox_templates = (MediaWikiParsedLink("Template:Item/styles.css", False),)
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)
    sources = read_repo_page_sources(manifest, tmp_path)
    snapshots = wiki.get_page_snapshots([entry.title for entry in manifest.entries])
    ordered = prepare_repo_page_checks(manifest, sources, snapshots, wiki)
    reports = []
    render_repo_page_checks(ordered, sources, snapshots, wiki, catalog={}, dry_run=True, report=reports.append)
    assert [entry.title for entry in ordered.entries] == ["Template:Item/styles.css", "Template:Item"]
    assert next(report for report in reports if report.title == "Template:Item").provisional
    assert wiki.writes == []


@pytest.mark.parametrize(
    "call",
    [
        "frame:extensionTag('templatestyles', '', { src = 'Template:Icon/styles.css' })",
        'frame:extensionTag("templatestyles", "", { src = "Icon/styles.css" })',
        "frame:extensionTag({ name = 'templatestyles', args = { src = 'Template:Icon/styles.css' } })",
        'frame:extensionTag { name = "templatestyles", args = { src = "Template:Icon/styles.css" } }',
        "frame:extensionTag(\n 'templatestyles', '', {\n src = 'Template:Icon/styles.css'\n })",
    ],
)
def test_lua_literal_templatestyles_dependency(call: str) -> None:
    assert literal_dependencies("Module:Erenshor/Icon", call) == ("Template:Icon/styles.css",)


def test_lua_stylesheets_join_module_dependencies_and_deduplicate() -> None:
    text = """
    local Args = require("Module:Erenshor/Args")
    frame:extensionTag('templatestyles', '', { src = 'Template:Icon/styles.css' })
    frame:extensionTag({ name = 'templatestyles', args = { src = 'Template:Icon/styles.css' } })
    """
    assert literal_dependencies("Module:Erenshor/Icon", text) == (
        "Module:Erenshor/Args",
        "Template:Icon/styles.css",
    )


@pytest.mark.parametrize(
    "text",
    [
        "frame:extensionTag('templatestyles', '', { src = stylesheet })",
        "frame:extensionTag({ name = tag, args = { src = 'Template:Icon/styles.css' } })",
        "frame:extensionTag('ref', '', { src = 'Template:Icon/styles.css' })",
    ],
)
def test_lua_dynamic_stylesheet_or_other_tag_has_no_literal_dependency(text: str) -> None:
    assert literal_dependencies("Module:Erenshor/Icon", text) == ()


def test_stylesheet_writes_before_the_lua_module_that_loads_it(tmp_path: Path) -> None:
    source(
        tmp_path,
        "wiki/modules/Erenshor/Icon.lua",
        "frame:extensionTag('templatestyles', '', { src = 'Template:Icon/styles.css' })",
    )
    source(tmp_path, "wiki/templates/Icon/styles.css", ".erenshor-icon { display: inline-block; }")
    wiki = Wiki({})
    deploy(tmp_path, wiki)
    assert wiki.writes == ["Template:Icon/styles.css", "Module:Erenshor/Icon"]


def test_lua_module_with_a_missing_stylesheet_stops_the_deploy(tmp_path: Path) -> None:
    source(
        tmp_path,
        "wiki/modules/Erenshor/Icon.lua",
        "frame:extensionTag({ name = 'templatestyles', args = { src = 'Template:Icon/styles.css' } })",
    )
    wiki = Wiki({})
    with pytest.raises(ValueError, match=r"Module:Erenshor/Icon needs missing page Template:Icon/styles\.css"):
        deploy(tmp_path, wiki)
    assert wiki.writes == []


def test_a_deploy_without_the_render_check_parses_nothing(tmp_path: Path) -> None:
    source(tmp_path, "wiki/templates/Item.wiki", "new")
    wiki = Wiki({"Template:Item": "old", "Example": "{{Item}}"}, {"Template:Item": ("Example",)})

    deploy(tmp_path, wiki)

    assert wiki.parsed == []
    assert wiki.writes == ["Template:Item"]
