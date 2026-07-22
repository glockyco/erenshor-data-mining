"""Tests for repo-owned wiki deployment manifests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from erenshor.application.wiki_deploy.manifest import (
    RepoWikiPageManifest,
    build_repo_page_manifest,
    read_repo_page_manifest,
    select_repo_page_manifest,
    write_repo_page_manifest,
)


def write_page(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_repo_page_manifest_maps_only_maintained_sources_to_wiki_titles(tmp_path: Path) -> None:
    """Repo modules and templates are deployable while generated variant data stays local-only."""
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "local p = {}\nreturn p\n")
    write_page(tmp_path, "wiki/modules/Erenshor/Item/Tooltip.lua", "local Tooltip = {}\nreturn Tooltip\n")
    write_page(tmp_path, "wiki/modules/Erenshor/Item/testcases.lua", "return {}\n")
    write_page(tmp_path, "wiki/templates/Item.wiki", "<includeonly>{{#invoke:Erenshor/Item|field}}</includeonly>\n")
    write_page(tmp_path, "wiki/templates/ArmorTable/Row.wiki", "<includeonly>|-</includeonly>\n")
    write_page(
        tmp_path,
        "variants/main/wiki/lua/Erenshor/Data/Items/Weapons.lua",
        "return { ['item:ember_longsword'] = {} }\n",
    )

    manifest = build_repo_page_manifest(tmp_path, variant="main")

    entries = {entry.title: entry for entry in manifest.entries}
    assert set(entries) == {
        "Module:Erenshor/Item",
        "Module:Erenshor/Item/Tooltip",
    }
    assert entries["Module:Erenshor/Item"].source_path == "wiki/modules/Erenshor/Item.lua"
    assert entries["Module:Erenshor/Item"].content_model == "Scribunto"
    assert all(not entry.source_path.startswith("variants/") for entry in manifest.entries)

    template_manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)
    template_entries = {entry.title: entry for entry in template_manifest.entries}
    assert {"Template:ArmorTable/Row", "Template:Item"} <= set(template_entries)
    assert template_entries["Template:ArmorTable/Row"].source_path == "wiki/templates/ArmorTable/Row.wiki"
    assert template_entries["Template:ArmorTable/Row"].content_model == "wikitext"


def test_select_repo_page_manifest_rejects_explicit_templates_without_opt_in(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    write_page(tmp_path, "wiki/templates/Item.wiki", "{{Item}}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)

    with pytest.raises(ValueError, match="Template pages require --include-templates: Template:Item"):
        select_repo_page_manifest(
            manifest,
            requested_titles={"Module:Erenshor/Item", "Template:Item"},
        )


def test_select_repo_page_manifest_includes_templates_only_with_opt_in(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    write_page(tmp_path, "wiki/templates/Item.wiki", "{{Item}}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)

    selected = select_repo_page_manifest(
        manifest,
        include_templates=True,
        known_live_titles={"Module:Erenshor/Data/Links"},
    )

    assert [entry.title for entry in selected.entries] == ["Module:Erenshor/Item", "Template:Item"]


def test_build_repo_page_manifest_excludes_interface_sources(tmp_path: Path) -> None:
    """Ordinary deployment excludes gadget CSS/JS while preserving canonical page order."""
    write_page(tmp_path, "wiki/gadgets/erenshor.css", ".item-tooltip { color: #fff; }\n")
    write_page(tmp_path, "wiki/gadgets/erenshor.js", "console.log('interface');\n")
    write_page(tmp_path, "wiki/templates/Item.wiki", "<includeonly>x</includeonly>\n")
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "local p = {}\nreturn p\n")
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Items.lua", "return {}\n")

    manifest = build_repo_page_manifest(tmp_path, variant="main")

    assert [entry.title for entry in manifest.entries] == [
        "Module:Erenshor/Item",
    ]
    assert all(not entry.title.startswith("MediaWiki:Gadget-") for entry in manifest.entries)
    assert all(not entry.source_path.startswith("wiki/gadgets/") for entry in manifest.entries)


def test_build_repo_page_manifest_hashes_source_bytes(tmp_path: Path) -> None:
    """Manifest source hashes are SHA-256 of exact repo file bytes."""
    content = "<includeonly>{{ItemTooltip}}</includeonly>\n"
    write_page(tmp_path, "wiki/templates/ItemTooltip.wiki", content)

    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)

    [entry] = manifest.entries
    assert entry.title == "Template:ItemTooltip"
    assert entry.source_sha256 == hashlib.sha256(content.encode()).hexdigest()


def test_build_repo_page_manifest_marks_real_cargo_declarations_only(tmp_path: Path) -> None:
    """Only actual declaring templates are flagged as Cargo declarations, not documentation mirrors."""
    write_page(
        tmp_path,
        "wiki/templates/Item.wiki",
        "<includeonly>{{#invoke:Erenshor/Item|cargoStore}}</includeonly>"
        "<noinclude>{{#cargo_declare:\n_table=Items\n|Page=Page\n}}</noinclude>\n",
    )
    write_page(
        tmp_path,
        "wiki/templates/Item/CargoDeclare.wiki",
        "<noinclude><pre>{{#cargo_declare:\n_table=Items\n|Page=Page\n}}</pre></noinclude>\n",
    )

    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)

    entries = {entry.title: entry for entry in manifest.entries}
    assert entries["Template:Item"].declares_cargo_table is True
    assert entries["Template:Item"].cargo_tables == ("Items",)
    assert entries["Template:Item"].ownership_class == "cargo_declaration"
    assert entries["Template:Item/CargoDeclare"].declares_cargo_table is False
    assert entries["Template:Item/CargoDeclare"].cargo_tables == ()
    assert entries["Template:Item/CargoDeclare"].ownership_class == "template"


def test_build_repo_page_manifest_orders_uploads_safely(tmp_path: Path) -> None:
    """Upload order is Lua modules, Cargo declarations, then other templates."""
    write_page(tmp_path, "wiki/templates/WeaponTable.wiki", "{{#cargo_query:tables=Items}}\n")
    write_page(
        tmp_path,
        "wiki/templates/Item.wiki",
        "<noinclude>{{#cargo_declare:\n_table=Items\n|Page=Page\n}}</noinclude>\n",
    )
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "local p = {}\nreturn p\n")
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Items.lua", "return {}\n")
    write_page(tmp_path, "wiki/content/Category/Links.wiki", "__HIDDENCAT__\n")
    manifest = build_repo_page_manifest(
        tmp_path,
        variant="main",
        include_templates=True,
        include_generated_data=True,
        include_content_pages=True,
    )

    assert [entry.title for entry in manifest.entries] == [
        "Module:Erenshor/Data/Items",
        "Module:Erenshor/Item",
        "Template:Item",
        "Template:WeaponTable",
        "Category:Links",
    ]
    assert [entry.upload_stage for entry in manifest.entries] == [
        "generated_data",
        "lua_module",
        "cargo_declaration",
        "template",
        "content_page",
    ]


def test_build_repo_page_manifest_rejects_duplicate_titles_across_roots(tmp_path: Path) -> None:
    """Content and module sources cannot target the same wiki title."""
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    write_page(tmp_path, "wiki/content/Module/Erenshor/Item.wiki", "Duplicate source\n")

    with pytest.raises(ValueError) as error:
        build_repo_page_manifest(tmp_path, variant="main", include_content_pages=True)

    message = str(error.value)
    assert "Duplicate wiki page title 'Module:Erenshor/Item'" in message
    assert "wiki/modules/Erenshor/Item.lua (stage lua_module)" in message
    assert "wiki/content/Module/Erenshor/Item.wiki (stage content_page)" in message


def test_build_repo_page_manifest_includes_selected_variant_data_and_content_only_with_opt_in(tmp_path: Path) -> None:
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Links.lua", "return {}\n")
    write_page(tmp_path, "variants/playtest/wiki/lua/Erenshor/Data/Links.lua", "return 'playtest'\n")
    write_page(tmp_path, "wiki/content/Category/Pages_with_unresolved_Erenshor_links.wiki", "__HIDDENCAT__\n")

    default_manifest = build_repo_page_manifest(tmp_path, variant="main")
    assert [entry.title for entry in default_manifest.entries] == []

    manifest = build_repo_page_manifest(
        tmp_path,
        variant="main",
        include_generated_data=True,
        include_content_pages=True,
    )
    assert [entry.title for entry in manifest.entries] == [
        "Module:Erenshor/Data/Links",
        "Category:Pages_with_unresolved_Erenshor_links",
    ]
    assert manifest.entries[0].upload_stage == "generated_data"
    assert manifest.entries[1].upload_stage == "content_page"
    assert manifest.entries[0].source_path.startswith("variants/main/")


def test_build_repo_page_manifest_discovers_requested_optional_titles_without_broadening_defaults(
    tmp_path: Path,
) -> None:
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Links.lua", "return {}\n")
    write_page(tmp_path, "wiki/templates/Item.wiki", "{{Item}}\n")
    write_page(tmp_path, "wiki/content/Category/Links.wiki", "__HIDDENCAT__\n")

    default_manifest = build_repo_page_manifest(tmp_path, variant="main")
    assert [entry.title for entry in default_manifest.entries] == []

    requested_titles = {"Module:Erenshor/Data/Links", "Template:Item", "Category:Links"}
    discoverable_manifest = build_repo_page_manifest(
        tmp_path,
        variant="main",
        requested_titles=requested_titles,
    )
    assert [entry.title for entry in discoverable_manifest.entries] == [
        "Module:Erenshor/Data/Links",
        "Template:Item",
        "Category:Links",
    ]

    with pytest.raises(ValueError, match="Template pages require --include-templates: Template:Item"):
        select_repo_page_manifest(discoverable_manifest, requested_titles=requested_titles)

    with pytest.raises(ValueError, match="Generated data pages require explicit deployment opt-in"):
        select_repo_page_manifest(
            discoverable_manifest,
            requested_titles={"Module:Erenshor/Data/Links"},
        )

    with pytest.raises(ValueError, match="Content pages require explicit deployment opt-in: Category:Links"):
        select_repo_page_manifest(
            discoverable_manifest,
            requested_titles={"Category:Links"},
        )

    selected = select_repo_page_manifest(
        discoverable_manifest,
        requested_titles=requested_titles,
        include_templates=True,
        include_generated_data=True,
        include_content_pages=True,
    )
    assert [entry.title for entry in selected.entries] == [
        "Module:Erenshor/Data/Links",
        "Template:Item",
        "Category:Links",
    ]


def test_select_repo_page_manifest_enforces_independent_opt_ins(tmp_path: Path) -> None:
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Links.lua", "return {}\n")
    write_page(tmp_path, "wiki/content/Category/Links.wiki", "__HIDDENCAT__\n")
    manifest = build_repo_page_manifest(
        tmp_path,
        variant="main",
        include_generated_data=True,
        include_content_pages=True,
    )

    with pytest.raises(ValueError, match="Generated data pages require explicit deployment opt-in"):
        select_repo_page_manifest(manifest, requested_titles={"Module:Erenshor/Data/Links"})
    with pytest.raises(ValueError, match="Content pages require explicit deployment opt-in"):
        select_repo_page_manifest(manifest, requested_titles={"Category:Links"})

    selected = select_repo_page_manifest(
        manifest,
        requested_titles={"Module:Erenshor/Data/Links", "Category:Links"},
        include_generated_data=True,
        include_content_pages=True,
    )
    assert [entry.title for entry in selected.entries] == [
        "Module:Erenshor/Data/Links",
        "Category:Links",
    ]


def test_resolver_selection_requires_data_links_dependency_or_known_live(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Link.lua", "return {}\n")
    write_page(tmp_path, "wiki/modules/Erenshor/AbilityLink.lua", "return {}\n")
    default_manifest = build_repo_page_manifest(tmp_path, variant="main")
    with pytest.raises(ValueError, match="Generated data pages require explicit deployment opt-in"):
        select_repo_page_manifest(default_manifest, requested_titles={"Module:Erenshor/Data/Links"})

    manifest = build_repo_page_manifest(tmp_path, variant="main")
    with pytest.raises(ValueError, match="requires Module:Erenshor/Data/Links"):
        select_repo_page_manifest(manifest, requested_titles={"Module:Erenshor/Link"})

    selected = select_repo_page_manifest(
        manifest,
        requested_titles={"Module:Erenshor/Link", "Module:Erenshor/AbilityLink"},
        known_live_titles={"Module:Erenshor/Data/Links"},
    )
    assert [entry.title for entry in selected.entries] == [
        "Module:Erenshor/AbilityLink",
        "Module:Erenshor/Link",
    ]


def test_item_selection_requires_data_links_dependency_or_known_live(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "return {}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")

    with pytest.raises(ValueError, match="requires Module:Erenshor/Data/Links"):
        select_repo_page_manifest(manifest, requested_titles={"Module:Erenshor/Item"})

    selected = select_repo_page_manifest(
        manifest,
        requested_titles={"Module:Erenshor/Item"},
        known_live_titles={"Module:Erenshor/Data/Links"},
    )
    assert [entry.title for entry in selected.entries] == ["Module:Erenshor/Item"]


def test_resolver_dependency_accepts_earlier_data_links_or_known_live(tmp_path: Path) -> None:
    write_page(tmp_path, "variants/main/wiki/lua/Erenshor/Data/Links.lua", "return {}\n")
    write_page(tmp_path, "wiki/modules/Erenshor/Link.lua", "return {}\n")
    write_page(tmp_path, "wiki/modules/Erenshor/Link/Search.lua", "return {}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_generated_data=True)
    selected = select_repo_page_manifest(
        manifest,
        requested_titles={"Module:Erenshor/Data/Links", "Module:Erenshor/Link", "Module:Erenshor/Link/Search"},
        include_generated_data=True,
    )
    assert [entry.title for entry in selected.entries] == [
        "Module:Erenshor/Data/Links",
        "Module:Erenshor/Link",
        "Module:Erenshor/Link/Search",
    ]

    live_manifest = build_repo_page_manifest(tmp_path, variant="main")
    selected_live = select_repo_page_manifest(
        live_manifest,
        requested_titles={"Module:Erenshor/Link", "Module:Erenshor/Link/Search"},
        known_live_titles={"Module:Erenshor/Data/Links"},
    )
    assert [entry.title for entry in selected_live.entries] == [
        "Module:Erenshor/Link",
        "Module:Erenshor/Link/Search",
    ]


def test_repo_page_manifest_round_trips_deployment_metadata(tmp_path: Path) -> None:
    """Persisted manifests preserve deployment metadata needed for rollback."""
    write_page(tmp_path, "wiki/templates/Item.wiki", "{{#cargo_declare:_table=Items}}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)
    [entry] = manifest.entries
    deployed_manifest = RepoWikiPageManifest(
        entries=(
            replace(
                entry,
                old_revision_id=100,
                old_revision_timestamp="2026-06-04T12:00:00Z",
                new_revision_id=101,
                new_revision_timestamp="2026-06-04T12:01:00Z",
                rollback_text_source="rollback/Template_Item.wiki",
                deploy_action="edited",
                null_edit_targets=("Ember Longsword",),
            ),
        )
    )
    output_path = tmp_path / "deploy-manifest.json"

    write_repo_page_manifest(deployed_manifest, output_path)
    reloaded = read_repo_page_manifest(output_path)

    assert reloaded == deployed_manifest
