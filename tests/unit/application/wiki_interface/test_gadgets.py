from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from erenshor.application.wiki_interface.gadgets import (
    GadgetDefinition,
    GadgetSourcePage,
    GadgetSpec,
    GadgetSpecError,
    gadget_source_pages,
    load_gadget_spec,
    reconcile_definition,
    render_definition_lines,
)


def write_spec(root: Path, text: str, *sources: str) -> None:
    gadget_root = root / "wiki" / "gadgets"
    gadget_root.mkdir(parents=True)
    (gadget_root / "gadgets.toml").write_text(text, encoding="utf-8")
    for source in sources:
        path = gadget_root / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source\n", encoding="utf-8")


def test_load_and_render_repository_gadget_spec() -> None:
    spec = load_gadget_spec(Path.cwd())

    assert spec.owned_names == ("erenshor", "item-tooltips", "semantic-link-picker")
    assert spec.gadgets == (
        GadgetDefinition(
            name="erenshor",
            options=("ResourceLoader", "default", "hidden", "type=styles"),
            sources=("erenshor.css",),
        ),
        GadgetDefinition(
            name="item-tooltips",
            options=("ResourceLoader", "default", "hidden"),
            sources=("item-tooltips.js",),
        ),
        GadgetDefinition(
            name="semantic-link-picker",
            options=("ResourceLoader", "default", "rights=edit"),
            sources=(
                "semantic-link-picker-core.js",
                "semantic-link-picker.js",
                "semantic-link-picker.css",
            ),
        ),
    )
    assert render_definition_lines(spec) == (
        "* erenshor[ResourceLoader|default|hidden|type=styles]|erenshor.css",
        "* item-tooltips[ResourceLoader|default|hidden]|item-tooltips.js",
        (
            "* semantic-link-picker[ResourceLoader|default|rights=edit]|"
            "semantic-link-picker-core.js|semantic-link-picker.js|semantic-link-picker.css"
        ),
    )
    with pytest.raises(FrozenInstanceError):
        spec.gadgets = ()  # type: ignore[misc]


def test_source_mapping_exposes_titles_paths_and_content_models(tmp_path: Path) -> None:
    write_spec(
        tmp_path,
        """owned_names = ["assets"]
[[gadgets]]
name = "assets"
options = ["ResourceLoader", "default"]
sources = ["theme.css", "loader.js", "config.json", "component.vue"]
""",
        "theme.css",
        "loader.js",
        "config.json",
        "component.vue",
    )

    assert gadget_source_pages(load_gadget_spec(tmp_path), tmp_path) == (
        GadgetSourcePage(
            title="MediaWiki:Gadget-theme.css",
            source_path=Path("wiki/gadgets/theme.css"),
            content_model="css",
        ),
        GadgetSourcePage(
            title="MediaWiki:Gadget-loader.js",
            source_path=Path("wiki/gadgets/loader.js"),
            content_model="javascript",
        ),
        GadgetSourcePage(
            title="MediaWiki:Gadget-config.json",
            source_path=Path("wiki/gadgets/config.json"),
            content_model="json",
        ),
        GadgetSourcePage(
            title="MediaWiki:Gadget-component.vue",
            source_path=Path("wiki/gadgets/component.vue"),
            content_model="vue",
        ),
    )


@pytest.mark.parametrize(
    ("toml", "sources", "message"),
    [
        (
            """owned_names = ["same"]
[[gadgets]]
name = "same"
options = ["ResourceLoader"]
sources = ["a.css"]
[[gadgets]]
name = "same"
options = ["ResourceLoader"]
sources = ["b.css"]
""",
            ("a.css", "b.css"),
            "duplicate gadget name",
        ),
        (
            """owned_names = ["one", "two"]
[[gadgets]]
name = "one"
options = ["ResourceLoader"]
sources = ["a.css"]
[[gadgets]]
name = "two"
options = ["ResourceLoader"]
sources = ["a.css"]
""",
            ("a.css",),
            "duplicate gadget source",
        ),
        (
            """owned_names = ["one"]
[[gadgets]]
name = "one"\noptions = ["ResourceLoader"]\nsources = ["../a.css"]\n""",
            (),
            "safe relative path",
        ),
        (
            """owned_names = ["one"]
[[gadgets]]
name = "one"\noptions = ["ResourceLoader"]\nsources = ["a.txt"]\n""",
            ("a.txt",),
            "unsupported gadget source suffix",
        ),
        (
            """owned_names = ["one"]
[[gadgets]]
name = "one"\noptions = ["ResourceLoader", "type=styles"]\nsources = ["a.js"]\n""",
            ("a.js",),
            "non-CSS source",
        ),
    ],
)
def test_invalid_gadget_specs_are_rejected(tmp_path: Path, toml: str, sources: tuple[str, ...], message: str) -> None:
    write_spec(tmp_path, toml, *sources)
    with pytest.raises(GadgetSpecError, match=message):
        load_gadget_spec(tmp_path)


def test_missing_and_unallowlisted_sources_are_rejected(tmp_path: Path) -> None:
    write_spec(
        tmp_path,
        """owned_names = ["one"]
[[gadgets]]
name = "one"
options = ["ResourceLoader"]
sources = ["declared.css"]
""",
        "declared.css",
        "forgotten.js",
    )
    with pytest.raises(GadgetSpecError, match="allowlisted"):
        load_gadget_spec(tmp_path)

    (tmp_path / "wiki" / "gadgets" / "forgotten.js").unlink()
    (tmp_path / "wiki" / "gadgets" / "declared.css").unlink()
    with pytest.raises(GadgetSpecError, match="does not exist"):
        load_gadget_spec(tmp_path)


def test_reconcile_replaces_managed_duplicates_and_preserves_datatables() -> None:
    spec = GadgetSpec(
        owned_names=("erenshor",),
        gadgets=(
            GadgetDefinition(
                name="erenshor",
                options=("ResourceLoader", "default", "hidden", "type=styles"),
                sources=("erenshor.css",),
            ),
        ),
    )
    existing = (
        "# keep this comment exactly\n"
        "* datatables[ResourceLoader|default]|datatables.js|datatables.css\n"
        "  * erenshor[ResourceLoader|hidden]|old.css\n"
        "* erenshor[ResourceLoader|default]|duplicate.css\n"
        "* unrelated[ResourceLoader|default]|unrelated.js\n"
    )

    assert reconcile_definition(existing, spec) == (
        "# keep this comment exactly\n"
        "* datatables[ResourceLoader|default]|datatables.js|datatables.css\n"
        "* erenshor[ResourceLoader|default|hidden|type=styles]|erenshor.css\n"
        "* unrelated[ResourceLoader|default]|unrelated.js\n"
    )


def test_reconcile_appends_when_absent_and_is_idempotent() -> None:
    spec = GadgetSpec(
        owned_names=("erenshor",),
        gadgets=(GadgetDefinition(name="erenshor", options=("ResourceLoader",), sources=("erenshor.css",)),),
    )
    existing = "* datatables[ResourceLoader|default]|datatables.js\n"

    reconciled = reconcile_definition(existing, spec)
    assert reconciled == existing + "* erenshor[ResourceLoader]|erenshor.css\n"
    assert reconcile_definition(reconciled, spec) == reconciled
    assert reconciled.endswith("\n") and not reconciled.endswith("\n\n")


def test_reconcile_retires_removed_owned_definition() -> None:
    spec = GadgetSpec(
        owned_names=("retired", "current"),
        gadgets=(GadgetDefinition(name="current", options=("ResourceLoader",), sources=("current.js",)),),
    )
    existing = (
        "* unrelated[ResourceLoader|default]|unrelated.js\n"
        "* retired[ResourceLoader|default]|old.js\n"
        "* retired[ResourceLoader|hidden]|old.js\n"
        "* keep[ResourceLoader|default]|keep.js\n"
    )

    assert reconcile_definition(existing, spec) == (
        "* unrelated[ResourceLoader|default]|unrelated.js\n"
        "* current[ResourceLoader]|current.js\n"
        "* keep[ResourceLoader|default]|keep.js\n"
    )


def test_reconcile_rename_removes_old_name_and_inserts_new_name() -> None:
    spec = GadgetSpec(
        owned_names=("old-name", "new-name"),
        gadgets=(GadgetDefinition(name="new-name", options=("ResourceLoader",), sources=("new.js",)),),
    )
    existing = (
        "* before[ResourceLoader]|before.js\n* old-name[ResourceLoader]|old.js\n* after[ResourceLoader]|after.js\n"
    )

    assert reconcile_definition(existing, spec) == (
        "* before[ResourceLoader]|before.js\n* new-name[ResourceLoader]|new.js\n* after[ResourceLoader]|after.js\n"
    )


def test_reconcile_preserves_crlf_style_and_unrelated_bytes() -> None:
    spec = GadgetSpec(
        owned_names=("retired", "current"),
        gadgets=(GadgetDefinition(name="current", options=("ResourceLoader",), sources=("current.js",)),),
    )
    existing = (
        "# keep exactly\r\n"
        "* retired[ResourceLoader|default]|old.js\r\n"
        "  * unrelated[ResourceLoader|default]|unrelated.js  \r\n"
    )

    assert reconcile_definition(existing, spec) == (
        "# keep exactly\r\n"
        "* current[ResourceLoader]|current.js\r\n"
        "  * unrelated[ResourceLoader|default]|unrelated.js  \r\n"
    )
    assert "\n" not in reconcile_definition(existing, spec).replace("\r\n", "")


def test_malformed_ownership_contract_is_rejected(tmp_path: Path) -> None:
    malformed = (
        "gadgets = []\n",
        'owned_names = ["same", "same"]\ngadgets = []\n',
        'owned_names = ["bad name"]\ngadgets = []\n',
        'owned_names = ["other"]\n'
        "[[gadgets]]\n"
        'name = "active"\n'
        'options = ["ResourceLoader"]\n'
        'sources = ["active.js"]\n',
        'owned_names = ["active"]\ngadgets = []\nextra = true\n',
    )
    for index, toml in enumerate(malformed):
        root = tmp_path / str(index)
        sources = ("active.js",) if index == 3 else ()
        write_spec(root, toml, *sources)
        with pytest.raises(GadgetSpecError):
            load_gadget_spec(root)
