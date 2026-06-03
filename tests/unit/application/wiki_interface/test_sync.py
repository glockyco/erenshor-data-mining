from __future__ import annotations

from pathlib import Path

import pytest

from erenshor.application.wiki_interface.sync import (
    MediaWikiInterfacePage,
    MissingInterfacePageError,
    gadget_source_titles,
    sync_interface_pages,
)


class FakeInterfaceClient:
    def __init__(self, pages: dict[str, str], media_files: dict[str, bytes] | None = None) -> None:
        self.pages = pages
        self.media_files = media_files or {}
        self.direct_media_files: dict[str, bytes] = {}
        self.requested: list[str] = []
        self.requested_media: list[str] = []
        self.requested_direct_media: list[str] = []

    def raw_page(self, title: str) -> str | None:
        self.requested.append(title)
        return self.pages.get(title)

    def media_file(self, title: str) -> bytes | None:
        self.requested_media.append(title)
        return self.media_files.get(title)

    def media_file_by_path(self, path: str) -> bytes | None:
        self.requested_direct_media.append(path)
        return self.direct_media_files.get(path)


def test_gadget_source_titles_reads_definition_sources() -> None:
    definition = """
    * datatables[ResourceLoader|dependencies=jquery|default]|datatables-lib.js|datatables.css
    * disabled[ResourceLoader|hidden]|disabled.json|disabled.vue
    """

    assert gadget_source_titles(definition) == [
        "MediaWiki:Gadget-datatables-lib.js",
        "MediaWiki:Gadget-datatables.css",
        "MediaWiki:Gadget-disabled.json",
        "MediaWiki:Gadget-disabled.vue",
    ]


def test_sync_fetches_fixed_pages_and_referenced_gadget_sources(tmp_path: Path) -> None:
    client = FakeInterfaceClient(
        {
            "MediaWiki:Common.css": "body { color: white; }\n",
            "MediaWiki:Vector.css": "#mw-page-base { background: black; }\n",
            "MediaWiki:Common.js": "window.erenshorCommon = true;\n",
            "MediaWiki:Vector.js": "window.erenshorVector = true;\n",
            "MediaWiki:Gadgets-definition": "* datatables[ResourceLoader|default]|datatables.js|datatables.css\n",
            "MediaWiki:Gadget-datatables.js": "window.datatables = true;\n",
            "MediaWiki:Gadget-datatables.css": ".datatable { width: 100%; }\n",
        }
    )

    result = sync_interface_pages(client=client, output_root=tmp_path, dry_run=False)

    assert client.requested == [
        "MediaWiki:Common.css",
        "MediaWiki:Vector.css",
        "MediaWiki:Common.js",
        "MediaWiki:Vector.js",
        "MediaWiki:Gadgets-definition",
        "MediaWiki:Gadget-datatables.js",
        "MediaWiki:Gadget-datatables.css",
    ]
    assert [page.title for page in result.pages] == client.requested
    assert (tmp_path / "MediaWiki" / "Common.css").read_text(encoding="utf-8") == "body { color: white; }\n"
    assert (tmp_path / "MediaWiki" / "Gadget-datatables.js").read_text(
        encoding="utf-8"
    ) == "window.datatables = true;\n"


def test_sync_mirrors_css_referenced_wiki_image_assets(tmp_path: Path) -> None:
    client = FakeInterfaceClient(
        {
            "MediaWiki:Common.css": ".box { background: url(/images/8/80/Site-background.jpg); }\n",
            "MediaWiki:Vector.css": ".border { border-image-source: url('images/d/d8/Tooltip_border_top.png'); }\n",
            "MediaWiki:Common.js": "",
            "MediaWiki:Vector.js": "",
            "MediaWiki:Gadgets-definition": "",
        },
        {
            "File:Site-logo.png": b"site-logo",
            "File:Site-favicon.ico": b"site-favicon",
            "File:Site-background.jpg": b"site-background",
            "File:Tooltip_border_top.png": b"tooltip-border",
        },
    )
    image_root = tmp_path / "images"

    result = sync_interface_pages(
        client=client, output_root=tmp_path / "interface", image_root=image_root, dry_run=False
    )

    assert client.requested_media[-2:] == ["File:Site-background.jpg", "File:Tooltip_border_top.png"]
    assert [asset.title for asset in result.assets][-2:] == [
        "File:Site-background.jpg",
        "File:Tooltip_border_top.png",
    ]
    assert (image_root / "8" / "80" / "Site-background.jpg").read_bytes() == b"site-background"
    assert (image_root / "d" / "d8" / "Tooltip_border_top.png").read_bytes() == b"tooltip-border"


def test_sync_mirrors_fixed_live_skin_assets(tmp_path: Path) -> None:
    client = FakeInterfaceClient(
        {
            "MediaWiki:Common.css": "",
            "MediaWiki:Vector.css": "",
            "MediaWiki:Common.js": "",
            "MediaWiki:Vector.js": "",
            "MediaWiki:Gadgets-definition": "",
        }
    )
    client.direct_media_files = {
        "/images/Site-logo.png": b"site-logo",
        "/images/Site-favicon.ico": b"site-favicon",
    }
    image_root = tmp_path / "images"

    result = sync_interface_pages(
        client=client, output_root=tmp_path / "interface", image_root=image_root, dry_run=False
    )

    assert [asset.path for asset in result.assets] == [
        image_root / "Site-logo.png",
        image_root / "Site-favicon.ico",
    ]
    assert (image_root / "Site-logo.png").read_bytes() == b"site-logo"
    assert (image_root / "Site-favicon.ico").read_bytes() == b"site-favicon"


def test_sync_reports_unresolvable_live_css_assets_without_blocking(tmp_path: Path) -> None:
    client = FakeInterfaceClient(
        {
            "MediaWiki:Common.css": ".box { background: url(/images/e/e0/MP_banner.jpg); }\n",
            "MediaWiki:Vector.css": "",
            "MediaWiki:Common.js": "",
            "MediaWiki:Vector.js": "",
            "MediaWiki:Gadgets-definition": "",
        },
        {
            "File:Site-logo.png": b"site-logo",
            "File:Site-favicon.ico": b"site-favicon",
        },
    )

    result = sync_interface_pages(
        client=client, output_root=tmp_path / "interface", image_root=tmp_path / "images", dry_run=False
    )

    assert [asset.title for asset in result.assets] == ["File:Site-logo.png", "File:Site-favicon.ico"]
    assert [asset.source_path for asset in result.missing_assets] == ["/images/e/e0/MP_banner.jpg"]


def test_sync_reports_diff_before_overwriting_existing_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "MediaWiki" / "Common.css"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("body { color: red; }\n", encoding="utf-8")
    client = FakeInterfaceClient(
        {
            "MediaWiki:Common.css": "body { color: white; }\n",
            "MediaWiki:Vector.css": "",
            "MediaWiki:Common.js": "",
            "MediaWiki:Vector.js": "",
            "MediaWiki:Gadgets-definition": "",
        }
    )

    result = sync_interface_pages(client=client, output_root=tmp_path, dry_run=False)

    common_css = next(page for page in result.pages if page.title == "MediaWiki:Common.css")
    assert common_css.diff.startswith("--- wiki-dev/interface/MediaWiki/Common.css")
    assert "-body { color: red; }" in common_css.diff
    assert "+body { color: white; }" in common_css.diff
    assert snapshot.read_text(encoding="utf-8") == "body { color: white; }\n"


def test_sync_dry_run_does_not_overwrite_existing_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "MediaWiki" / "Common.css"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text("body { color: red; }\n", encoding="utf-8")
    client = FakeInterfaceClient(
        {
            "MediaWiki:Common.css": "body { color: white; }\n",
            "MediaWiki:Vector.css": "",
            "MediaWiki:Common.js": "",
            "MediaWiki:Vector.js": "",
            "MediaWiki:Gadgets-definition": "",
        }
    )

    result = sync_interface_pages(client=client, output_root=tmp_path, dry_run=True)

    assert result.pages[0] == MediaWikiInterfacePage(
        title="MediaWiki:Common.css",
        path=tmp_path / "MediaWiki" / "Common.css",
        content="body { color: white; }\n",
        diff=result.pages[0].diff,
        changed=True,
    )
    assert snapshot.read_text(encoding="utf-8") == "body { color: red; }\n"


def test_sync_fails_loudly_on_missing_interface_page(tmp_path: Path) -> None:
    client = FakeInterfaceClient({"MediaWiki:Common.css": ""})

    with pytest.raises(MissingInterfacePageError, match=r"MediaWiki:Vector\.css"):
        sync_interface_pages(client=client, output_root=tmp_path, dry_run=False)
