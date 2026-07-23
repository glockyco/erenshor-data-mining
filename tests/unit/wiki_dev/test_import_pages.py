from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_import_pages() -> ModuleType:
    script = Path("wiki-dev/import_pages.py")
    module_spec = importlib.util.spec_from_file_location("wiki_dev_import_pages", script)
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
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


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeWikiClient:
    def __init__(
        self,
        pages: dict[str, tuple[str, str]],
        *,
        failing_edits: set[str] | None = None,
    ) -> None:
        self.pages = dict(pages)
        self.failing_edits = failing_edits or set()
        self.gets: list[dict[str, str]] = []
        self.posts: list[dict[str, str]] = []

    def get(self, endpoint: str, *, params: dict[str, str]) -> _FakeResponse:
        del endpoint
        self.gets.append(dict(params))
        titles = params["titles"].split("|")
        response_pages: list[dict[str, object]] = []
        for title in titles:
            remote = self.pages.get(title)
            if remote is None:
                response_pages.append({"title": title, "missing": True})
                continue
            content, content_model = remote
            response_pages.append(
                {
                    "title": title,
                    "pageid": len(response_pages) + 1,
                    "contentmodel": content_model,
                    "revisions": [
                        {
                            "contentmodel": content_model,
                            "content": content,
                            "slots": {"main": {"content": content, "contentmodel": content_model, "*": content}},
                        }
                    ],
                }
            )
        return _FakeResponse({"query": {"pages": response_pages}})

    def post(
        self,
        endpoint: str,
        *,
        data: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> _FakeResponse:
        del endpoint, params
        self.posts.append(dict(data))
        action = data["action"]
        title = data.get("title", data.get("titles", ""))
        if action == "edit":
            if title in self.failing_edits:
                return _FakeResponse({"error": {"code": "failed", "info": "simulated failure"}})
            normalized_text = data["text"].rstrip(" \n\r\t\v\0").replace("\r\n", "\n").replace("\r", "\n")
            previous_model = self.pages.get(title, ("", "wikitext"))[1]
            self.pages[title] = (normalized_text, data.get("contentmodel", previous_model))
            return _FakeResponse({"edit": {"result": "Success"}})
        if action == "delete":
            self.pages.pop(title, None)
            return _FakeResponse({"delete": {"title": title}})
        if action == "purge":
            return _FakeResponse({"purge": [{"title": title, "purged": True}]})
        raise AssertionError(f"unexpected mutation action: {action}")


def _make_pages(import_pages: ModuleType, root: Path, contents: dict[str, str]):
    pages = []
    for index, (title, content) in enumerate(contents.items()):
        source = root / "sources" / f"page-{index}.wiki"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(content, encoding="utf-8")
        pages.append(import_pages.PageSource(title=title, path=source))
    return pages


def _remote_pages(pages, contents: dict[str, str], content_model: str = "wikitext"):
    return {
        page.title: (
            contents[page.title].rstrip(" \n\r\t\v\0").replace("\r\n", "\n").replace("\r", "\n"),
            content_model,
        )
        for page in pages
        if page.title in contents
    }


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


def test_content_models_are_deterministic(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    module_path = root / "wiki" / "modules" / "Example.lua"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("return { answer = 42 }\n", encoding="utf-8")

    pages = import_pages.discover_pages(root)
    by_title = {page.title: page for page in pages}
    assert by_title["Module:Example"].content_model == "Scribunto"
    assert by_title["MediaWiki:Gadget-tooltip.css"].content_model == "css"
    assert by_title["MediaWiki:Gadget-tooltip.js"].content_model == "javascript"
    assert by_title["MediaWiki:Common.css"].content_model == "css"
    assert import_pages.PageSource(title="Template:Default", path=root / "default.wiki").content_model == "wikitext"

    manifest = import_pages.build_manifest(root, pages)
    assert list(manifest) == sorted(manifest)
    css_entry = manifest["MediaWiki:Gadget-tooltip.css"]
    assert css_entry.source_path == "wiki/gadgets/tooltip.css"
    assert css_entry.content_model == "css"
    assert css_entry.sha256 == hashlib.sha256((root / "wiki" / "gadgets" / "tooltip.css").read_bytes()).hexdigest()

    manifest_file = import_pages.manifest_path(root)
    assert manifest_file == root / "wiki-dev" / "runtime" / "import_pages.manifest.json"
    import_pages.write_manifest(manifest_file, manifest)
    first_bytes = manifest_file.read_bytes()
    assert first_bytes.endswith(b"\n")
    serialized = json.loads(first_bytes)
    assert serialized["schema_version"] == 1
    assert list(serialized["pages"]) == sorted(serialized["pages"])
    assert serialized["pages"]["MediaWiki:Gadget-tooltip.css"] == {
        "source_path": "wiki/gadgets/tooltip.css",
        "content_model": "css",
        "sha256": css_entry.sha256,
    }
    assert import_pages.load_manifest(manifest_file) == manifest
    import_pages.write_manifest(manifest_file, import_pages.build_manifest(root, pages))
    assert manifest_file.read_bytes() == first_bytes


def test_missing_page_is_created_with_declared_content_model(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    source = root / "sources" / "gadget.js"
    source.parent.mkdir(parents=True)
    source.write_text("window.gadget = true;\n", encoding="utf-8")
    pages = [
        import_pages.PageSource(
            title="MediaWiki:Gadget-managed.js",
            path=source,
            content_model="javascript",
        )
    ]
    client = _FakeWikiClient({})

    report = import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert report.created == ("MediaWiki:Gadget-managed.js",)
    edit = next(post for post in client.posts if post["action"] == "edit")
    assert edit["createonly"] == "1"
    assert edit["contentmodel"] == "javascript"
    assert client.pages["MediaWiki:Gadget-managed.js"] == ("window.gadget = true;", "javascript")


def test_storage_normalization_does_not_trigger_updates(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(
        import_pages,
        root,
        {"Template:Normalized": "first  \r\nsecond \t\r\n"},
    )
    client = _FakeWikiClient({"Template:Normalized": ("first  \nsecond", "wikitext")})

    report = import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert report.unchanged == ("Template:Normalized",)
    assert report.created == report.updated == report.deleted == report.purged == ()
    assert client.posts == []


def test_first_reconciliation_creates_updates_and_purges_only_changed_pages(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(
        import_pages,
        root,
        {"Template:Missing": "new page\n", "Template:Drifted": "local\n", "Template:Stable": "same\n"},
    )
    client = _FakeWikiClient(_remote_pages(pages, {"Template:Drifted": "remote\n", "Template:Stable": "same\n"}))

    report = import_pages.reconcile_pages(client, "https://wiki.test/api.php", "token", pages, root)

    assert report.created == ("Template:Missing",)
    assert report.updated == ("Template:Drifted",)
    assert report.unchanged == ("Template:Stable",)
    assert report.deleted == ()
    assert report.purged == ("Template:Missing", "Template:Drifted")
    assert client.pages["Template:Missing"] == ("new page", "wikitext")
    assert client.pages["Template:Drifted"] == ("local", "wikitext")
    assert {post["titles"] for post in client.posts if post["action"] == "purge"} == {
        "Template:Missing",
        "Template:Drifted",
    }


def test_identical_reconciliation_has_no_mutations_and_preserves_manifest_bytes(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(import_pages, root, {"Template:One": "one\n", "Template:Two": "two\n"})
    client = _FakeWikiClient(_remote_pages(pages, {"Template:One": "one\n", "Template:Two": "two\n"}))
    import_pages.reconcile_pages(client, "endpoint", "token", pages, root)
    manifest_file = import_pages.manifest_path(root)
    before = manifest_file.read_bytes()
    client.posts.clear()

    report = import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert report.created == report.updated == report.deleted == report.purged == ()
    assert report.unchanged == ("Template:One", "Template:Two")
    assert client.posts == []
    assert manifest_file.read_bytes() == before


def test_one_local_edit_updates_only_that_page_and_purges_it(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(
        import_pages,
        root,
        {"Template:One": "one\n", "Template:Two": "two\n", "Template:Three": "three\n"},
    )
    client = _FakeWikiClient(
        _remote_pages(
            pages,
            {"Template:One": "one\n", "Template:Two": "two\n", "Template:Three": "three\n"},
        )
    )
    import_pages.reconcile_pages(client, "endpoint", "token", pages, root)
    pages[1].path.write_text("two edited\n", encoding="utf-8")
    client.posts.clear()

    report = import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert report.created == report.deleted == ()
    assert report.updated == ("Template:Two",)
    assert report.unchanged == ("Template:One", "Template:Three")
    assert report.purged == ("Template:Two",)
    assert [post["title"] for post in client.posts if post["action"] == "edit"] == ["Template:Two"]
    assert [post["titles"] for post in client.posts if post["action"] == "purge"] == ["Template:Two"]


def test_removed_managed_title_is_deleted_but_not_purged(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    all_pages = _make_pages(
        import_pages,
        root,
        {"Template:Keep": "keep\n", "Template:Remove": "remove\n"},
    )
    client = _FakeWikiClient(
        _remote_pages(all_pages, {"Template:Keep": "keep\n", "Template:Remove": "remove\n"})
        | {"Template:Unmanaged": ("do not touch\n", "wikitext")}
    )
    import_pages.reconcile_pages(client, "endpoint", "token", all_pages, root)
    current_pages = [all_pages[0]]
    client.posts.clear()

    report = import_pages.reconcile_pages(client, "endpoint", "token", current_pages, root)

    assert report.created == report.updated == report.purged == ()
    assert report.unchanged == ("Template:Keep",)
    assert report.deleted == ("Template:Remove",)
    assert "Template:Remove" not in client.pages
    assert "Template:Unmanaged" in client.pages
    assert [post["action"] for post in client.posts] == ["delete"]
    assert client.posts[0]["title"] == "Template:Remove"


def test_unmanaged_remote_pages_are_not_queried_or_changed(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(import_pages, root, {"Template:Managed": "managed\n"})
    client = _FakeWikiClient(
        {
            "Template:Managed": ("managed\n", "wikitext"),
            "Template:Unmanaged": ("unmanaged\n", "wikitext"),
        }
    )

    report = import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert report.unchanged == ("Template:Managed",)
    assert all("Template:Unmanaged" not in request["titles"] for request in client.gets)
    assert client.pages["Template:Unmanaged"] == ("unmanaged\n", "wikitext")
    assert client.posts == []


def test_content_model_mismatch_fails_closed_before_mutation(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(import_pages, root, {"Template:Page": "local\n"})
    client = _FakeWikiClient({"Template:Page": ("remote\n", "Scribunto")})

    with pytest.raises(RuntimeError, match="content model"):
        import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert client.posts == []
    assert not import_pages.manifest_path(root).exists()


def test_malformed_prior_manifest_fails_before_mutation(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(import_pages, root, {"Template:Page": "local\n"})
    manifest_file = import_pages.manifest_path(root)
    manifest_file.parent.mkdir(parents=True)
    manifest_file.write_text("{not valid json", encoding="utf-8")
    client = _FakeWikiClient({"Template:Page": ("remote\n", "wikitext")})

    with pytest.raises(ValueError):
        import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert client.posts == []
    assert manifest_file.read_text(encoding="utf-8") == "{not valid json"


def test_mutation_failure_preserves_prior_manifest_bytes(tmp_path: Path) -> None:
    import_pages = load_import_pages()
    root = make_root(tmp_path)
    pages = _make_pages(import_pages, root, {"Template:Page": "local\n"})
    manifest_file = import_pages.manifest_path(root)
    import_pages.write_manifest(manifest_file, import_pages.build_manifest(root, pages))
    before = manifest_file.read_bytes()
    client = _FakeWikiClient({"Template:Page": ("remote\n", "wikitext")}, failing_edits={"Template:Page"})

    with pytest.raises(RuntimeError, match="Edit failed"):
        import_pages.reconcile_pages(client, "endpoint", "token", pages, root)

    assert manifest_file.read_bytes() == before
    assert [post["action"] for post in client.posts] == ["edit"]
