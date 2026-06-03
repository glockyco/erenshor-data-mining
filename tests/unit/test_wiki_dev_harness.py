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


def test_maps_repo_module_and_template_files_to_wiki_titles(tmp_path: Path) -> None:
    root = tmp_path
    (root / "wiki/modules/Erenshor/Data").mkdir(parents=True)
    (root / "wiki/templates").mkdir(parents=True)
    (root / "wiki-dev/fixtures/pages").mkdir(parents=True)

    (root / "wiki/modules/Erenshor/Item.lua").write_text("return {}\n", encoding="utf-8")
    (root / "wiki/modules/Erenshor/Data/Items.lua").write_text("return {}\n", encoding="utf-8")
    (root / "wiki/templates/Item.wiki").write_text("{{#invoke:Erenshor/Item|render}}\n", encoding="utf-8")
    (root / "wiki-dev/fixtures/pages/Sword_of_Flames.wiki").write_text("{{Item}}\n", encoding="utf-8")

    import_pages = load_script("wiki-dev/import_pages.py")

    pages = import_pages.discover_pages(root)

    assert [(page.title, page.path.relative_to(root).as_posix()) for page in pages] == [
        ("Module:Erenshor/Data/Items", "wiki/modules/Erenshor/Data/Items.lua"),
        ("Module:Erenshor/Item", "wiki/modules/Erenshor/Item.lua"),
        ("Template:Item", "wiki/templates/Item.wiki"),
        ("Sword of Flames", "wiki-dev/fixtures/pages/Sword_of_Flames.wiki"),
    ]


def test_builds_mediawiki_api_urls_without_double_slashes() -> None:
    import_pages = load_script("wiki-dev/import_pages.py")

    assert import_pages.api_url("http://localhost:8088") == "http://localhost:8088/api.php"
    assert import_pages.api_url("http://localhost:8088/") == "http://localhost:8088/api.php"


def test_smoke_check_reports_missing_expected_text() -> None:
    smoke_test = load_script("wiki-dev/smoke_test.py")

    result = smoke_test.check_rendered_html(
        title="Sword of Flames",
        html="<p>Rendered sword page</p>",
        expected=["Rendered sword page", "Damage"],
    )

    assert result.ok is False
    assert result.missing == ["Damage"]
    assert result.title == "Sword of Flames"


def test_smoke_check_accepts_all_expected_text() -> None:
    smoke_test = load_script("wiki-dev/smoke_test.py")

    result = smoke_test.check_rendered_html(
        title="Sword of Flames",
        html="<p>Rendered sword page with Damage</p>",
        expected=["Rendered sword page", "Damage"],
    )

    assert result.ok is True
    assert result.missing == []


def test_smoke_check_rejects_parser_health_markers() -> None:
    smoke_test = load_script("wiki-dev/smoke_test.py")

    html = """
    <div class="mw-parser-output">
      <strong class="error">Lua error</strong>
      <strong class="error">Script error</strong>
      <p><strong class="error">Parser function failed</strong></p>
      <a class="new" title="Template:Missing">Template:Missing</a>
      <!-- WARNING: Post-expand include size limit exceeded. -->
    </div>
    """

    result = smoke_test.check_rendered_html(title="Broken Item", html=html, expected=[])

    assert result.ok is False
    assert result.missing == [
        "forbidden parser output: Lua error",
        "forbidden parser output: Script error",
        "forbidden parser output: parser error",
        "forbidden parser output: unresolved template",
        "forbidden parser output: parser limit report",
    ]


def test_smoke_check_allows_successful_newpp_limit_reports() -> None:
    smoke_test = load_script("wiki-dev/smoke_test.py")

    html = """
    <div class="mw-parser-output">
      <p>Rendered page</p>
      <!--
      NewPP limit report
      Expensive parser function count: 0/100
      -->
    </div>
    """

    result = smoke_test.check_rendered_html(title="Healthy Page", html=html, expected=["Rendered page"])

    assert result.ok is True
    assert result.missing == []


def test_smoke_check_allows_healthy_template_links_and_visible_limit_text() -> None:
    smoke_test = load_script("wiki-dev/smoke_test.py")

    html = """
    <div class="mw-parser-output">
      <p>Documented TemplateSandbox page</p>
      <a href="/wiki/Template:Item" title="Template:Item">Template:Item</a>
      <p>A guide may describe what to do when a limit exceeded message appears.</p>
    </div>
    """

    result = smoke_test.check_rendered_html(
        title="Healthy Template Docs",
        html=html,
        expected=["Documented TemplateSandbox page"],
    )

    assert result.ok is True
    assert result.missing == []


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
