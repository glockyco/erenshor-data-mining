from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_import_pages() -> ModuleType:
    script = Path("wiki-dev/import_pages.py")
    module_spec = importlib.util.spec_from_file_location("wiki_dev_import_pages", script)
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def make_root(tmp_path: Path) -> Path:
    root = tmp_path
    gadget_root = root / "wiki" / "gadgets"
    gadget_root.mkdir(parents=True)
    (gadget_root / "gadgets.toml").write_text(
        """owned_names = ["tooltip"]

[[gadgets]]
name = "tooltip"
options = ["ResourceLoader", "default"]
sources = ["tooltip.css", "tooltip.js"]
""",
        encoding="utf-8",
    )
    (gadget_root / "tooltip.css").write_text(".tooltip { color: red; }\n", encoding="utf-8")
    (gadget_root / "tooltip.js").write_text("window.tooltip = true;\n", encoding="utf-8")

    interface = root / "wiki-dev" / "interface" / "MediaWiki"
    interface.mkdir(parents=True)
    for name in (
        "Common.css",
        "Vector.css",
        "Common.js",
        "Vector.js",
        "Sidebar",
        "Mainpage-description",
        "Recentchanges",
        "Randompage",
        "Help-mediawiki",
    ):
        (interface / name).write_text("\n", encoding="utf-8")
    (interface / "Gadgets-definition").write_text(
        "# keep this comment\n"
        "* datatables[ResourceLoader|default]|datatables.js|datatables.css\n"
        "* tooltip[ResourceLoader]|old.css\n",
        encoding="utf-8",
    )
    # These are stale synced copies and must not compete with repository sources.
    (interface / "Gadget-tooltip.css").write_text("stale css\n", encoding="utf-8")
    (interface / "Gadget-tooltip.js").write_text("stale js\n", encoding="utf-8")
    (interface / "Gadget-datatables.js").write_text("window.datatables = true;\n", encoding="utf-8")
    return root


def test_discovery_uses_unique_allowlisted_titles_and_includes_javascript(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)

    pages = import_pages.discover_pages(root)
    titles = [page.title for page in pages]
    managed = [title for title in titles if title.startswith("MediaWiki:Gadget-tooltip")]

    assert len(titles) == len(set(titles))
    assert managed == ["MediaWiki:Gadget-tooltip.css", "MediaWiki:Gadget-tooltip.js"]
    assert titles.index("MediaWiki:Gadget-tooltip.css") < titles.index("MediaWiki:Gadget-tooltip.js")
    assert titles[-1] == "MediaWiki:Gadgets-definition"
    javascript = next(page for page in pages if page.title == "MediaWiki:Gadget-tooltip.js")
    assert javascript.path == root / "wiki" / "gadgets" / "tooltip.js"
    assert import_pages.page_content(javascript) == "window.tooltip = true;\n"


def test_interface_definition_reconciliation_is_idempotent(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    spec = import_pages.load_gadget_spec(root)
    assert spec is not None

    existing = (root / "wiki-dev" / "interface" / "MediaWiki" / "Gadgets-definition").read_text(encoding="utf-8")
    reconciled = import_pages.reconcile_definition(existing, spec)

    assert import_pages.reconcile_definition(reconciled, spec) == reconciled
    definition_page = next(
        page
        for page in import_pages.discover_interface_pages(root, spec=spec)
        if page.title == "MediaWiki:Gadgets-definition"
    )
    assert import_pages.page_content(definition_page) == reconciled


def test_unrelated_definition_lines_survive_managed_reconciliation(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    spec = import_pages.load_gadget_spec(root)
    assert spec is not None

    existing = (root / "wiki-dev" / "interface" / "MediaWiki" / "Gadgets-definition").read_text(encoding="utf-8")
    reconciled = import_pages.reconcile_definition(existing, spec)

    assert "# keep this comment\n" in reconciled
    assert "* datatables[ResourceLoader|default]|datatables.js|datatables.css\n" in reconciled
    assert reconciled.count("* tooltip[") == 1
    assert "* tooltip[ResourceLoader|default]|tooltip.css|tooltip.js\n" in reconciled
