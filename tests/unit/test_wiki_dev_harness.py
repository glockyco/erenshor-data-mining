from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_script(path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_maps_interface_repo_and_fixture_pages_to_wiki_titles(tmp_path: Path) -> None:
    root = tmp_path
    (root / "wiki/modules/Erenshor").mkdir(parents=True)
    (root / "wiki/templates").mkdir(parents=True)
    (root / "wiki-dev/interface/MediaWiki").mkdir(parents=True)
    (root / "wiki-dev/fixtures/modules/Erenshor/Data/Items").mkdir(parents=True)
    (root / "wiki-dev/fixtures/pages").mkdir(parents=True)

    (root / "wiki-dev/interface/theme-shim.css").write_text(":root { --wiki-content-border-color: #866806; }\n")
    (root / "wiki-dev/interface/theme-shim.js").write_text(
        "document.documentElement.classList.add('theme-dark');\n",
        encoding="utf-8",
    )
    (root / "wiki-dev/interface/MediaWiki/Common.css").write_text("body { color: white; }\n", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Vector.css").write_text("", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Common.js").write_text("", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Vector.js").write_text("", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Gadgets-definition").write_text("", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Sidebar").write_text("* navigation\n", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Mainpage-description").write_text("Main Page", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Recentchanges").write_text("Recent Changes", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Randompage").write_text("Random Page", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Help-mediawiki").write_text("MediaWiki Help", encoding="utf-8")
    (root / "wiki-dev/interface/MediaWiki/Gadget-datatables.js").write_text("window.datatables = true;\n")
    (root / "wiki/modules/Erenshor/Item.lua").write_text("return {}\n", encoding="utf-8")
    (root / "wiki-dev/fixtures/modules/Erenshor/Data/Items.lua").write_text("return {}\n", encoding="utf-8")
    (root / "wiki-dev/fixtures/modules/Erenshor/Data/Items/Weapons.lua").write_text("return {}\n", encoding="utf-8")
    (root / "wiki/templates/Item.wiki").write_text("{{#invoke:Erenshor/Item|render}}\n", encoding="utf-8")
    (root / "wiki-dev/fixtures/pages/Sword_of_Flames.wiki").write_text("{{Item}}\n", encoding="utf-8")

    import_pages = load_script("wiki-dev/import_pages.py")

    pages = import_pages.discover_pages(root)

    assert [(page.title, page.path.relative_to(root).as_posix()) for page in pages] == [
        ("MediaWiki:Common.css", "wiki-dev/interface/MediaWiki/Common.css"),
        ("MediaWiki:Common.js", "wiki-dev/interface/MediaWiki/Common.js"),
        ("MediaWiki:Gadget-datatables.js", "wiki-dev/interface/MediaWiki/Gadget-datatables.js"),
        ("MediaWiki:Gadgets-definition", "wiki-dev/interface/MediaWiki/Gadgets-definition"),
        ("MediaWiki:Help-mediawiki", "wiki-dev/interface/MediaWiki/Help-mediawiki"),
        ("MediaWiki:Mainpage-description", "wiki-dev/interface/MediaWiki/Mainpage-description"),
        ("MediaWiki:Randompage", "wiki-dev/interface/MediaWiki/Randompage"),
        ("MediaWiki:Recentchanges", "wiki-dev/interface/MediaWiki/Recentchanges"),
        ("MediaWiki:Sidebar", "wiki-dev/interface/MediaWiki/Sidebar"),
        ("MediaWiki:Vector.css", "wiki-dev/interface/MediaWiki/Vector.css"),
        ("MediaWiki:Vector.js", "wiki-dev/interface/MediaWiki/Vector.js"),
        ("Module:Erenshor/Item", "wiki/modules/Erenshor/Item.lua"),
        ("Module:Erenshor/Data/Items", "wiki-dev/fixtures/modules/Erenshor/Data/Items.lua"),
        ("Module:Erenshor/Data/Items/Weapons", "wiki-dev/fixtures/modules/Erenshor/Data/Items/Weapons.lua"),
        ("Template:Item", "wiki/templates/Item.wiki"),
        ("Sword of Flames", "wiki-dev/fixtures/pages/Sword_of_Flames.wiki"),
    ]
    common_css = pages[0]
    assert common_css.content.startswith(":root { --wiki-content-border-color: #866806; }\n")
    assert common_css.content.endswith("body { color: white; }\n")
    common_js = pages[1]
    assert common_js.content.startswith("document.documentElement.classList.add('theme-dark');\n")


def test_discover_pages_fails_when_interface_mirror_is_missing(tmp_path: Path) -> None:
    import_pages = load_script("wiki-dev/import_pages.py")

    try:
        import_pages.discover_pages(tmp_path)
    except RuntimeError as error:
        assert "uv run erenshor wiki sync-interface" in str(error)
    else:
        raise AssertionError("missing interface mirror did not fail")


def test_builds_mediawiki_api_urls_without_double_slashes() -> None:
    import_pages = load_script("wiki-dev/import_pages.py")

    assert import_pages.api_url("http://localhost:8088") == "http://localhost:8088/api.php"
    assert import_pages.api_url("http://localhost:8088/") == "http://localhost:8088/api.php"


def test_smoke_check_reports_missing_expected_text() -> None:
    render = load_script("wiki-dev/smoke/render.py")

    result = render.check_rendered_html(
        title="Sword of Flames",
        html="<p>Rendered sword page</p>",
        expected=["Rendered sword page", "Damage"],
    )

    assert result.ok is False
    assert result.missing == ["Damage"]
    assert result.title == "Sword of Flames"


def test_smoke_check_accepts_all_expected_text() -> None:
    render = load_script("wiki-dev/smoke/render.py")

    result = render.check_rendered_html(
        title="Sword of Flames",
        html="<p>Rendered sword page with Damage</p>",
        expected=["Rendered sword page", "Damage"],
    )

    assert result.ok is True
    assert result.missing == []


def test_smoke_check_rejects_parser_health_markers() -> None:
    render = load_script("wiki-dev/smoke/render.py")

    html = """
    <div class="mw-parser-output">
      <strong class="error">Lua error</strong>
      <strong class="error">Script error</strong>
      <p><strong class="error">Parser function failed</strong></p>
      <a class="new" title="Template:Missing">Template:Missing</a>
      <!-- WARNING: Post-expand include size limit exceeded. -->
    </div>
    """

    result = render.check_rendered_html(title="Broken Item", html=html, expected=[])

    assert result.ok is False
    assert result.missing == [
        "forbidden parser output: Lua error",
        "forbidden parser output: Script error",
        "forbidden parser output: parser error",
        "forbidden parser output: unresolved template",
        "forbidden parser output: parser limit report",
    ]


def test_smoke_check_allows_successful_newpp_limit_reports() -> None:
    render = load_script("wiki-dev/smoke/render.py")

    html = """
    <div class="mw-parser-output">
      <p>Rendered page</p>
      <!--
      NewPP limit report
      Expensive parser function count: 0/100
      -->
    </div>
    """

    result = render.check_rendered_html(title="Healthy Page", html=html, expected=["Rendered page"])

    assert result.ok is True
    assert result.missing == []


def test_smoke_check_allows_healthy_template_links_and_visible_limit_text() -> None:
    render = load_script("wiki-dev/smoke/render.py")

    html = """
    <div class="mw-parser-output">
      <p>Documented TemplateSandbox page</p>
      <a href="/wiki/Template:Item" title="Template:Item">Template:Item</a>
      <p>A guide may describe what to do when a limit exceeded message appears.</p>
    </div>
    """

    result = render.check_rendered_html(
        title="Healthy Template Docs",
        html=html,
        expected=["Documented TemplateSandbox page"],
    )

    assert result.ok is True
    assert result.missing == []


def test_cargo_check_reports_missing_and_mismatched_item_rows() -> None:
    cargo = load_script("wiki-dev/smoke/cargo.py")

    expectations = [
        cargo.CargoItemExpectation(
            page="Ember Longsword",
            fields={
                "StableKey": "item:ember_longsword",
                "Name": "Ember Longsword",
                "Type": "Weapon",
                "Damage": "18",
            },
        ),
        cargo.CargoItemExpectation(
            page="Ember Longsword",
            fields={
                "StableKey": "item:shared_page",
                "Name": "Shared Page Variant",
                "Type": "Weapon",
                "Damage": "5",
            },
        ),
        cargo.CargoItemExpectation(
            page="Abyssal Plate",
            fields={
                "StableKey": "item:abyssal_plate",
                "Name": "Abyssal Plate",
                "Type": "Armor",
                "Armor": "40",
            },
        ),
    ]
    rows = [
        {
            "Page": "Ember Longsword",
            "StableKey": "item:ember_longsword",
            "Name": "Wrong Name",
            "Type": "Weapon",
            "Damage": "17",
        },
        {
            "Page": "Ember Longsword",
            "StableKey": "item:duplicate",
            "Name": "Duplicate",
            "Type": "Weapon",
            "Damage": "18",
        },
        {
            "Page": "Ember Longsword",
            "StableKey": "item:shared_page",
            "Name": "Shared Page Variant",
            "Type": "Weapon",
            "Damage": "5",
        },
        {
            "Page": "Ember Longsword",
            "StableKey": "item:shared_page",
            "Name": "Duplicate Shared Page Variant",
            "Type": "Weapon",
            "Damage": "5",
        },
        {
            "Page": "Unexpected Item",
            "StableKey": "item:unexpected",
            "Name": "Unexpected Item",
            "Type": "General",
        },
        {
            "Page": "Scratch Sandbox Item",
            "StableKey": "item:scratch",
            "Name": "Scratch Sandbox Item",
            "Type": "General",
        },
        {
            "Page": "Scratch Sandbox Item",
            "StableKey": "item:scratch",
            "Name": "Duplicate Scratch Sandbox Item",
            "Type": "General",
        },
    ]

    failures = cargo.check_cargo_item_rows(rows, expectations, absent_pages={"Unexpected Item"})

    assert failures == [
        "Cargo Items row Ember Longsword Name: expected Ember Longsword, got Wrong Name",
        "Cargo Items row Ember Longsword Damage: expected 18, got 17",
        "Cargo Items missing row for Abyssal Plate",
        "Cargo Items duplicate row for Ember Longsword / item:shared_page",
        "Cargo Items unexpected row for Ember Longsword / item:duplicate",
        "Cargo Items unexpected row for Unexpected Item",
    ]


def test_cargo_expectations_reject_duplicate_page_stable_key_pairs(tmp_path: Path) -> None:
    cargo = load_script("wiki-dev/smoke/cargo.py")
    expectations = tmp_path / "cargo_items.tsv"
    row_values = ["Page", "item:duplicate", "Name", "Type"]
    row_values.extend([""] * (len(cargo.CARGO_ITEM_FIELDS) - len(row_values) - 1))
    row_values.append("0")
    row = "\t".join(row_values)
    expectations.write_text(f"{row}\n{row}\n", encoding="utf-8")

    try:
        cargo.load_cargo_item_expectations(expectations)
    except ValueError as error:
        assert str(error) == f"{expectations}: duplicate expected Cargo row Page / item:duplicate"
    else:
        raise AssertionError("duplicate Cargo Page/StableKey pair was accepted")


def test_cargo_check_reports_missing_and_mismatched_character_rows() -> None:
    cargo = load_script("wiki-dev/smoke/cargo.py")
    expectations = [
        cargo.CargoCharacterExpectation(
            page="A Grizzly Bear",
            fields={
                "StableKey": "character:a_grizzly_bear",
                "Name": "A Grizzly Bear",
                "Type": "Enemy",
                "Level": "12",
            },
        ),
        cargo.CargoCharacterExpectation(
            page="Captain Rowan",
            fields={
                "StableKey": "character:captain_rowan",
                "Name": "Captain Rowan",
                "Type": "NPC",
                "Level": "20",
            },
        ),
    ]
    rows = [
        {
            "Page": "A Grizzly Bear",
            "StableKey": "character:a_grizzly_bear",
            "Name": "Wrong Bear",
            "Type": "Enemy",
            "Level": "11",
        },
        {
            "Page": "A Grizzly Bear",
            "StableKey": "character:duplicate",
            "Name": "Duplicate Bear",
            "Type": "Enemy",
        },
        {
            "Page": "A Grizzly Bear",
            "StableKey": "character:duplicate",
            "Name": "Duplicate Bear",
            "Type": "Enemy",
        },
        {
            "Page": "Scratch Character",
            "StableKey": "character:scratch",
            "Name": "Scratch Character",
            "Type": "NPC",
        },
    ]

    failures = cargo.check_cargo_character_rows(rows, expectations)

    assert failures == [
        "Cargo Characters row A Grizzly Bear Name: expected A Grizzly Bear, got Wrong Bear",
        "Cargo Characters row A Grizzly Bear Level: expected 12, got 11",
        "Cargo Characters missing row for Captain Rowan",
        "Cargo Characters duplicate row for A Grizzly Bear / character:duplicate",
        "Cargo Characters unexpected row for A Grizzly Bear / character:duplicate",
    ]


def test_compose_does_not_mount_local_settings_before_install() -> None:
    compose = Path("wiki-dev/compose.yml").read_text(encoding="utf-8")

    assert ":/var/www/html/LocalSettings.php" not in compose
    assert "./runtime:/workspace/wiki-dev-runtime" in compose
    assert "./LocalSettings.extra.php:/var/www/html/LocalSettings.extra.php:ro" in compose


def test_local_wiki_runtime_artifacts_are_ignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert "wiki-dev/db/" in gitignore
    assert "wiki-dev/images/" in gitignore
    assert "wiki-dev/runtime/" in gitignore


def test_scribunto_uses_system_lua_for_arm_compatible_local_rendering() -> None:
    dockerfile = Path("wiki-dev/Dockerfile").read_text(encoding="utf-8")
    settings = Path("wiki-dev/LocalSettings.extra.php").read_text(encoding="utf-8")

    assert "lua5.1" in dockerfile
    assert "$wgScribuntoEngineConf['luastandalone']['luaPath'] = '/usr/bin/lua5.1';" in settings


def test_local_mediawiki_matches_live_skin_gadget_and_article_size_surface() -> None:
    dockerfile = Path("wiki-dev/Dockerfile").read_text(encoding="utf-8")
    settings = Path("wiki-dev/LocalSettings.extra.php").read_text(encoding="utf-8")

    assert "/var/www/html/extensions/Gadgets" in dockerfile
    assert "wfLoadSkin( 'Vector' );" in settings
    assert "$wgDefaultSkin = 'vector';" in settings
    assert "$wgVectorDefaultSkinVersion = '1';" in settings
    assert "wfLoadExtension( 'Gadgets' );" in settings
    assert "$wgMaxArticleSize = 4096;" in settings
    assert "$wgTemplateSandboxEditNamespaces = [ NS_TEMPLATE, 828 ];" in settings
    assert "$wgTemplateSandboxEditNamespaces = true;" not in settings
    assert "$wgLogos = [ '1x' => '/images/Site-logo.png' ];" in settings
    assert "$wgFavicon = '/images/Site-favicon.ico';" in settings


def test_local_theme_shims_define_live_platform_variables() -> None:
    theme_css = Path("wiki-dev/interface/theme-shim.css").read_text(encoding="utf-8")
    theme_js = Path("wiki-dev/interface/theme-shim.js").read_text(encoding="utf-8")

    assert "--color-base: #ededed;" in theme_css
    assert "--border-color-base: #866806;" in theme_css
    assert "--background-color-interactive: #133759;" in theme_css
    assert "--wiki-sidebar-heading-color: #ededed;" in theme_css
    assert ".vector-menu-portal .vector-menu-heading-label" in theme_css
    assert ".vector-menu-portal .vector-menu-content .mw-list-item a:visited" in theme_css
    assert "color: var(--wiki-sidebar-link-color) !important;" in theme_css
    assert "color: var(--wiki-sidebar-heading-color) !important;" in theme_css
    assert ".portable-infobox .pi-data {" in theme_css
    assert "display: flex;" in theme_css
    assert ".portable-infobox .pi-title {" in theme_css
    assert ".portable-infobox .pi-horizontal-group {" in theme_css
    assert ".portable-infobox .pi-group {" in theme_css
    assert "border-bottom-style: solid;" in theme_css
    assert ".portable-infobox .pi-horizontal-group-item:not(:first-child)" in theme_css
    assert "border-left-style: solid;" in theme_css
    assert "background: none !important;" in theme_css
    assert '"wgg-dom-version-1_43"' in theme_js
    assert '"skin--responsive"' in theme_js
