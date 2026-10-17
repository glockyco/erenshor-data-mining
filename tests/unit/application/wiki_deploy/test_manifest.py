"""Tests for repo-owned wiki deployment manifests."""

from __future__ import annotations

import hashlib
import json
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
    write_page(tmp_path, "wiki/templates/Item/Quality.wiki", "<includeonly>|-</includeonly>\n")
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
    assert {"Template:Item/Quality", "Template:Item"} <= set(template_entries)
    assert template_entries["Template:Item/Quality"].source_path == "wiki/templates/Item/Quality.wiki"
    assert template_entries["Template:Item/Quality"].content_model == "wikitext"


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


def test_build_repo_page_manifest_keeps_stylesheets_as_sanitized_css_templates(tmp_path: Path) -> None:
    """A TemplateStyles stylesheet keeps its .css title and needs the template opt-in."""
    write_page(tmp_path, "wiki/templates/Character.wiki", '<templatestyles src="Template:Character/styles.css" />\n')
    write_page(tmp_path, "wiki/templates/Character/styles.css", ".pi-image { color: red; }\n")

    manifest = build_repo_page_manifest(tmp_path, variant="main", include_templates=True)

    entries = {entry.title: entry for entry in manifest.entries}
    stylesheet = entries["Template:Character/styles.css"]
    assert (stylesheet.content_model, stylesheet.upload_stage) == ("sanitized-css", "stylesheet")
    assert entries["Template:Character"].content_model == "wikitext"
    with pytest.raises(ValueError, match="Template pages require --include-templates"):
        select_repo_page_manifest(manifest, requested_titles={"Template:Character/styles.css"})


def test_build_repo_page_manifest_orders_uploads_safely(tmp_path: Path) -> None:
    """Upload order is stylesheets, generated data, Lua modules, templates, then content pages."""
    write_page(tmp_path, "wiki/templates/Item.wiki", "<includeonly>{{#invoke:Erenshor/Item|render}}</includeonly>\n")
    write_page(tmp_path, "wiki/modules/Erenshor/Item.lua", "local p = {}\nreturn p\n")
    write_page(tmp_path, "wiki/templates/Item/styles.css", ".item-icon { display: inline-block; }\n")
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
        "Template:Item/styles.css",
        "Module:Erenshor/Data/Items",
        "Module:Erenshor/Item",
        "Template:Item",
        "Category:Links",
    ]
    assert [entry.upload_stage for entry in manifest.entries] == [
        "stylesheet",
        "generated_data",
        "lua_module",
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


def test_repo_page_manifest_round_trips_deployment_metadata(tmp_path: Path) -> None:
    """Persisted manifests preserve deployment metadata needed for rollback."""
    write_page(tmp_path, "wiki/templates/Item.wiki", "Item template\n")
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
                pending_mutation=True,
                rollback_revision_id=102,
            ),
        ),
        api_url="https://wiki.example/api.php",
        variant="canary",
        wiki_root=str(tmp_path / "wiki"),
    )
    output_path = tmp_path / "deploy-manifest.json"

    write_repo_page_manifest(deployed_manifest, output_path)
    reloaded = read_repo_page_manifest(output_path)

    assert reloaded == deployed_manifest


def test_old_manifest_still_loads_without_attribution_or_pending_fields(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Example.lua", "return {}\n")
    path = tmp_path / "manifest.json"
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    write_repo_page_manifest(manifest, path)
    payload = json.loads(path.read_bytes())
    for key in ("api_url", "variant", "wiki_root"):
        payload.pop(key)
    for entry in payload["entries"]:
        entry.pop("pending_mutation")
        entry.pop("rollback_revision_id")
        entry.pop("pending_operation")
        entry.pop("pending_base_revision_id")
        entry.pop("pending_acknowledged_revision_id")
        entry.pop("requires_rollback")
        entry.pop("rollback_content_model")
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = read_repo_page_manifest(path)

    assert loaded.api_url is None
    assert loaded.variant is None
    assert loaded.wiki_root is None
    assert not loaded.entries[0].pending_mutation
    assert loaded.entries[0].rollback_revision_id is None
    assert loaded.entries[0].pending_operation is None
    assert loaded.entries[0].pending_base_revision_id is None
    assert loaded.entries[0].rollback_content_model is None


def test_manifest_filters_and_outcome_clones_keep_attribution(tmp_path: Path) -> None:
    from erenshor.application.wiki_deploy.dependencies import order_and_check_dependencies
    from erenshor.application.wiki_deploy.pages import RepoPageDeployResult, build_deployed_manifest

    write_page(tmp_path, "wiki/modules/Erenshor/Example.lua", "return {}\n")
    manifest = replace(
        build_repo_page_manifest(tmp_path, variant="main"),
        api_url="https://wiki.example/api.php",
        variant="canary",
        wiki_root=str(tmp_path / "wiki"),
    )
    selected = select_repo_page_manifest(manifest)
    ordered = order_and_check_dependencies(selected, {manifest.entries[0].title: "return {}\n"}, {})
    deployed = build_deployed_manifest(ordered, RepoPageDeployResult(entries=()))

    assert deployed == manifest


@pytest.mark.parametrize(
    "api_url",
    [
        "https://account:secret@wiki.example/api.php",
        "https://account@wiki.example/api.php",
        "https://:secret@wiki.example/api.php",
        "https://@wiki.example/api.php",
    ],
)
def test_manifest_rejects_endpoint_userinfo_without_echoing_secrets(api_url: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not contain credentials") as raised:
        RepoWikiPageManifest(entries=(), api_url=api_url)
    assert "account" not in str(raised.value)
    assert "secret" not in str(raised.value)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"entries": [], "api_url": api_url}), encoding="utf-8")
    with pytest.raises(ValueError, match="must not contain credentials"):
        read_repo_page_manifest(path)


def test_pending_request_intent_round_trips(tmp_path: Path) -> None:
    write_page(tmp_path, "wiki/modules/Erenshor/Example.lua", "return {}\n")
    manifest = build_repo_page_manifest(tmp_path, variant="main")
    [entry] = manifest.entries
    manifest = replace(
        manifest,
        entries=(
            replace(
                entry,
                pending_mutation=True,
                pending_operation="rollback",
                pending_base_revision_id=42,
                pending_acknowledged_revision_id=43,
                requires_rollback=True,
                rollback_content_model="json",
            ),
        ),
    )
    path = tmp_path / "manifest.json"
    write_repo_page_manifest(manifest, path)
    assert read_repo_page_manifest(path) == manifest
