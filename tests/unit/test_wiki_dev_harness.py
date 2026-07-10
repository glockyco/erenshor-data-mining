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


def test_smoke_check_rejects_unexpected_missing_data_categories() -> None:
    render = load_script("wiki-dev/smoke/render.py")

    result = render.check_rendered_html(
        title="Ember Longsword",
        html="<p>Rendered item</p>\nCategory:Pages_with_missing_Erenshor_item_data",
        expected=["Rendered item"],
    )

    assert result.ok is False
    assert result.missing == ["forbidden parser output: unexpected missing-data category"]


def test_smoke_check_rejects_raw_semantic_link_templates() -> None:
    render = load_script("wiki-dev/smoke/render.py")

    result = render.check_rendered_html(
        title="Minor Lightning",
        html="<p>{{ItemLink|Abyssal Plate}} {{AbilityLink|Minor Lightning}}</p>",
        expected=[],
    )

    assert result.ok is False
    assert result.missing == [
        "forbidden parser output: raw cross-reference template",
        "forbidden parser output: raw cross-reference template",
    ]


def test_smoke_fixture_runs_every_lua_testcase_module() -> None:
    expectations = Path("wiki-dev/fixtures/smoke.tsv").read_text(encoding="utf-8")
    testcase_modules = sorted(Path("wiki/modules/Erenshor").glob("**/testcases.lua"))

    expected_markers = {
        "PASS Erenshor " + "/".join(path.relative_to("wiki/modules/Erenshor").parts[:-1]) + " testcases"
        for path in testcase_modules
    }

    for marker in expected_markers:
        assert marker in expectations


def test_every_fixture_article_has_smoke_expectation() -> None:
    expectations = {
        line.split("\t", 1)[0]
        for line in Path("wiki-dev/fixtures/smoke.tsv").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    fixture_titles = {
        path.with_suffix("").relative_to("wiki-dev/fixtures/pages").as_posix().replace("_", " ")
        for path in Path("wiki-dev/fixtures/pages").glob("*.wiki")
    }

    assert sorted(fixture_titles - expectations) == []


def test_null_edit_discovers_pages_from_render_and_cargo_fixtures() -> None:
    null_edit = load_script("wiki-dev/null_edit.py")

    titles = null_edit.load_titles(
        Path("wiki-dev/fixtures/smoke.tsv"),
        Path("wiki-dev/fixtures/cargo_items.tsv"),
        Path("wiki-dev/fixtures/cargo_characters.tsv"),
    )

    assert titles[:3] == ["A Cat for a Deer", "A Grizzly Bear", "A Magical Sword in Port Azure"]
    assert "Manual Item Override" in titles
    assert "Captain Rowan" in titles
    assert len(titles) == len(set(titles))


def test_null_edit_purges_after_all_pages_refresh(monkeypatch) -> None:
    null_edit = load_script("wiki-dev/null_edit.py")
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        null_edit,
        "null_edit_page",
        lambda client, endpoint, token, title: calls.append(("edit", title)),
    )
    monkeypatch.setattr(
        null_edit,
        "purge_page",
        lambda client, endpoint, token, title: calls.append(("purge", title)),
    )

    null_edit.refresh_pages(object(), "api.php", "csrf", ["Cargo WeaponTable Smoke", "Ember Longsword"])

    assert calls == [
        ("edit", "Cargo WeaponTable Smoke"),
        ("edit", "Ember Longsword"),
        ("purge", "Cargo WeaponTable Smoke"),
        ("purge", "Ember Longsword"),
    ]


def test_cargo_check_declares_local_tables_to_recreate() -> None:
    cargo_check = load_script("wiki-dev/cargo_check.py")

    # Every recreatable table must map to exactly one declaring template, and the
    # recreate set must be in sync with that mapping (the invariant, not a literal
    # snapshot that breaks whenever a table is added).
    assert set(cargo_check.CARGO_TABLES) == set(cargo_check.CARGO_TEMPLATES_BY_TABLE)
    assert "Items" in cargo_check.CARGO_TABLES
    assert "AbilityClasses" in cargo_check.CARGO_TABLES
    assert cargo_check.CARGO_TEMPLATES_BY_TABLE["AbilityClasses"] == "AbilityClasses"


def test_obtained_from_identity_keeps_condition_variants_distinct() -> None:
    cargo = load_script("wiki-dev/smoke/cargo.py")
    expectations = [
        cargo.CargoExpectation(
            page="A Burgundy Skipper",
            fields={
                "ItemKey": "item:fish - a burgundy skipper",
                "SourceType": "fishing",
                "SourceKey": "water:brake:287.10:7.50:247.80",
                "SourceCondition": "day",
                "Probability": "5.9375",
            },
        ),
        cargo.CargoExpectation(
            page="A Burgundy Skipper",
            fields={
                "ItemKey": "item:fish - a burgundy skipper",
                "SourceType": "fishing",
                "SourceKey": "water:brake:287.10:7.50:247.80",
                "SourceCondition": "night",
                "Probability": "19",
            },
        ),
    ]
    rows = [
        {
            "Page": "A Burgundy Skipper",
            "ItemKey": "item:fish - a burgundy skipper",
            "SourceType": "fishing",
            "SourceKey": "water:brake:287.10:7.50:247.80",
            "SourceCondition": "day",
            "Probability": "5.9375",
        },
        {
            "Page": "A Burgundy Skipper",
            "ItemKey": "item:fish - a burgundy skipper",
            "SourceType": "fishing",
            "SourceKey": "water:brake:287.10:7.50:247.80",
            "SourceCondition": "night",
            "Probability": "19",
        },
    ]

    assert cargo.check_cargo_obtained_from_rows(rows, expectations) == []


def test_used_in_identity_keeps_use_types_and_targets_distinct() -> None:
    cargo = load_script("wiki-dev/smoke/cargo.py")
    expectations = [
        cargo.CargoExpectation(
            page="Copper Ore",
            fields={
                "ItemKey": "item:ore - copper ore",
                "UseType": "craft_material",
                "TargetKey": "item:template - copper armor mold",
                "Quantity": "2",
                "Slot": "1",
            },
        ),
        cargo.CargoExpectation(
            page="Copper Ore",
            fields={
                "ItemKey": "item:ore - copper ore",
                "UseType": "quest_requirement",
                "TargetKey": "quest:an ore for the forge",
                "Quantity": "1",
                "Slot": "",
            },
        ),
    ]
    rows = [
        {
            "Page": "Copper Ore",
            "ItemKey": "item:ore - copper ore",
            "UseType": "craft_material",
            "TargetKey": "item:template - copper armor mold",
            "Quantity": "2",
            "Slot": "1",
        },
        {
            "Page": "Copper Ore",
            "ItemKey": "item:ore - copper ore",
            "UseType": "quest_requirement",
            "TargetKey": "quest:an ore for the forge",
            "Quantity": "1",
            "Slot": "",
        },
    ]

    assert cargo.check_cargo_used_in_rows(rows, expectations) == []


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


def test_checked_in_drop_obtained_from_fixture_parity() -> None:
    parity = load_script("wiki-dev/parity/cargo_relations.py")
    cargo = load_script("wiki-dev/smoke/cargo.py")
    drops = parity.load_legacy_drop_expectations(Path("wiki-dev/fixtures/cargo_drops_parity.tsv"))
    obtained = cargo.load_cargo_obtained_from_expectations(Path("wiki-dev/fixtures/cargo_obtained_from.tsv"))

    assert parity.compare_drop_obtained_from_parity(drops, obtained) == []


def test_drop_obtained_from_parity_collapses_manual_override_pages() -> None:
    parity = load_script("wiki-dev/parity/cargo_relations.py")
    drops = [
        parity.RelationExpectation(
            page=page,
            fields={
                "CharacterKey": "character:a_grizzly_bear",
                "ItemKey": "item:bear_pelt",
                "DropProbability": "50",
                "IsGuaranteed": "1",
            },
        )
        for page in ("A Grizzly Bear", "Manual Character Override")
    ]
    obtained = [
        parity.RelationExpectation(
            page="Bear Pelt",
            fields={
                "ItemKey": "item:bear_pelt",
                "SourceType": "drop",
                "SourceKey": "character:a_grizzly_bear",
                "SourceText": "",
                "Probability": "50",
                "IsGuaranteed": "1",
                "Quantity": "",
                "SourceCondition": "",
                "Origin": "generated",
            },
        )
    ]

    assert parity.compare_drop_obtained_from_parity(drops, obtained) == []


def test_drop_obtained_from_parity_reports_missing_and_extra_rows() -> None:
    parity = load_script("wiki-dev/parity/cargo_relations.py")
    drop = parity.RelationExpectation(
        page="A Grizzly Bear",
        fields={
            "CharacterKey": "character:a_grizzly_bear",
            "ItemKey": "item:bear_meat",
            "DropProbability": "28.3",
            "IsGuaranteed": "0",
        },
    )
    extra = parity.RelationExpectation(
        page="Bear Meat",
        fields={
            "ItemKey": "item:bear_meat",
            "SourceType": "drop",
            "SourceKey": "character:other",
            "SourceText": "",
            "Probability": "1",
            "IsGuaranteed": "0",
            "Quantity": "",
            "SourceCondition": "",
            "Origin": "generated",
        },
    )

    failures = parity.compare_drop_obtained_from_parity([drop], [extra])

    assert failures == [
        "ObtainedFrom missing drop relation ('character:a_grizzly_bear', 'item:bear_meat', '28.3', '0') x1",
        "ObtainedFrom has extra drop relation ('character:other', 'item:bear_meat', '1', '0') x1",
    ]


def test_checked_in_container_drop_obtained_from_parity() -> None:
    parity = load_script("wiki-dev/parity/cargo_relations.py")
    cargo = load_script("wiki-dev/smoke/cargo.py")
    container_drops = parity.load_legacy_container_drop_expectations(
        Path("wiki-dev/fixtures/cargo_container_drops_parity.tsv")
    )
    obtained = cargo.load_cargo_obtained_from_expectations(Path("wiki-dev/fixtures/cargo_obtained_from.tsv"))

    assert parity.compare_container_drop_obtained_from_parity(container_drops, obtained) == []


def test_container_drop_obtained_from_parity_reports_missing_and_extra_rows() -> None:
    parity = load_script("wiki-dev/parity/cargo_relations.py")
    container_drop = parity.RelationExpectation(
        page="Magical Bag",
        fields={
            "SourceItemKey": "item:magical_bag",
            "DroppedItemKey": "item:bear_meat",
            "DropProbability": "20",
            "IsGuaranteed": "0",
        },
    )
    extra = parity.RelationExpectation(
        page="Bear Meat",
        fields={
            "ItemKey": "item:bear_meat",
            "SourceType": "item_use",
            "SourceKey": "item:other_bag",
            "SourceText": "",
            "Probability": "1",
            "IsGuaranteed": "0",
            "Quantity": "",
            "SourceCondition": "",
            "Origin": "generated",
        },
    )

    failures = parity.compare_container_drop_obtained_from_parity([container_drop], [extra])

    assert failures == [
        "ObtainedFrom missing item-use relation ('item:magical_bag', 'item:bear_meat', '20', '0') x1",
        "ObtainedFrom has extra item-use relation ('item:other_bag', 'item:bear_meat', '1', '0') x1",
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

    failures = cargo.check_cargo_character_rows(rows, expectations, absent_pages={"Scratch Character"})

    assert failures == [
        "Cargo Characters row A Grizzly Bear Name: expected A Grizzly Bear, got Wrong Bear",
        "Cargo Characters row A Grizzly Bear Level: expected 12, got 11",
        "Cargo Characters missing row for Captain Rowan",
        "Cargo Characters duplicate row for A Grizzly Bear / character:duplicate",
        "Cargo Characters unexpected row for A Grizzly Bear / character:duplicate",
        "Cargo Characters unexpected row for Scratch Character",
    ]


def test_compose_does_not_mount_local_settings_before_install() -> None:
    compose = Path("wiki-dev/compose.yml").read_text(encoding="utf-8")

    assert ":/var/www/html/LocalSettings.php" not in compose
    assert "./runtime:/workspace/wiki-dev-runtime" in compose
    assert "./LocalSettings.extra.php:/var/www/html/LocalSettings.extra.php:ro" in compose


def test_bootstrap_provisions_deploy_bot_in_bot_group() -> None:
    bootstrap = Path("wiki-dev/bootstrap.sh").read_text(encoding="utf-8")
    assert 'BOT_USER="${BOT_USER:-ErenshorBot}"' in bootstrap
    assert 'BOT_PASSWORD="${BOT_PASSWORD:-BotDevPassword-2026}"' in bootstrap
    assert 'createAndPromote --bot --force "$BOT_USER" "$BOT_PASSWORD"' in bootstrap


def test_extra_settings_do_not_grant_bot_cargo_recreate_right() -> None:
    # Cargo recreation runs as the cargo-admin (sysop) account, not the bot,
    # mirroring production where the deploy bot cannot hold this right.
    settings = Path("wiki-dev/LocalSettings.extra.php").read_text(encoding="utf-8")
    assert "$wgGroupPermissions['bot']['recreatecargodata']" not in settings


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
    assert "/var/www/html/extensions/PortableInfobox" in dockerfile
    assert "wfLoadExtension( 'PortableInfobox' );" in settings


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
    assert ":root.skin-theme-clientpref-night:not(.client-darkmode)" in theme_css
    assert "--pi-background: rgba(11, 26, 44, 0.1);" in theme_css
    assert '"wgg-dom-version-1_43"' in theme_js
    assert '"skin--responsive"' in theme_js
