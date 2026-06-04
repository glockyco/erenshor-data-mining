"""Tests for Cargo table recreation after declaration deploys."""

from __future__ import annotations

from collections.abc import Sequence

from erenshor.application.wiki_deploy.cargo import recreate_cargo_for_changed_declarations
from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest, RepoWikiPageManifestEntry
from erenshor.application.wiki_deploy.pages import RepoPageDeployResult, RepoPageDeployResultEntry


class RecordingCargoClient:
    def __init__(self, embeddedin: dict[str, tuple[str, ...]]) -> None:
        self.embeddedin = embeddedin
        self.recreate_tables_calls: list[tuple[str, str, str | None]] = []
        self.recreate_data_calls: list[tuple[str, str, int, str, str | None]] = []

    def recreate_cargo_tables(
        self,
        template_title: str,
        create_replacement: bool = False,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> None:
        self.recreate_tables_calls.append((template_title, assertion or "", assert_user))

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]:
        return self.embeddedin.get(title, ())

    def recreate_cargo_data(
        self,
        template_title: str,
        table: str,
        offset: int = 0,
        replace_old_rows: bool = True,
        assertion: str | None = None,
        assert_user: str | None = None,
    ) -> None:
        self.recreate_data_calls.append((template_title, table, offset, assertion or "", assert_user))


def _manifest(*entries: RepoWikiPageManifestEntry) -> RepoWikiPageManifest:
    return RepoWikiPageManifest(entries=entries)


def _declaring_entry(title: str, *tables: str) -> RepoWikiPageManifestEntry:
    return RepoWikiPageManifestEntry(
        title=title,
        source_path=f"wiki/templates/{title.removeprefix('Template:')}.wiki",
        source_sha256="0" * 64,
        ownership_class="cargo_declaration",
        upload_stage="cargo_declaration",
        content_model="wikitext",
        declares_cargo_table=True,
        cargo_tables=tables,
    )


def _changed(title: str) -> RepoPageDeployResultEntry:
    return RepoPageDeployResultEntry(
        title=title,
        status="changed",
        old_revision_id=1,
        old_revision_timestamp="2026-06-04T12:00:00Z",
        new_revision_id=2,
    )


def _unchanged(title: str) -> RepoPageDeployResultEntry:
    return RepoPageDeployResultEntry(
        title=title, status="unchanged", old_revision_id=None, old_revision_timestamp=None, new_revision_id=None
    )


def test_changed_declaration_recreates_schema_then_repopulates_data() -> None:
    """A changed Cargo-declaring template has its schema recreated and data repopulated."""
    manifest = _manifest(_declaring_entry("Template:Item", "Items"))
    deploy_result = RepoPageDeployResult(entries=(_changed("Template:Item"),))
    client = RecordingCargoClient({"Template:Item": ("Ember Longsword", "Abyssal Plate")})

    result = recreate_cargo_for_changed_declarations(
        client=client,
        manifest=manifest,
        deploy_result=deploy_result,
        namespaces=(0,),
        assertion="bot",
        assert_user="ErenshorBot",
    )

    assert client.recreate_tables_calls == [("Template:Item", "bot", "ErenshorBot")]
    assert client.recreate_data_calls == [("Template:Item", "Items", 0, "bot", "ErenshorBot")]
    [entry] = result.entries
    assert entry.template_title == "Template:Item"
    assert entry.tables == ("Items",)
    assert entry.using_page_count == 2


def test_unchanged_or_non_cargo_pages_are_not_recreated() -> None:
    """Only changed Cargo-declaring templates are recreated."""
    manifest = _manifest(
        _declaring_entry("Template:Item", "Items"),
        RepoWikiPageManifestEntry(
            title="Module:Erenshor/Item",
            source_path="wiki/modules/Erenshor/Item.lua",
            source_sha256="1" * 64,
            ownership_class="lua_module",
            upload_stage="lua_module",
            content_model="Scribunto",
            declares_cargo_table=False,
            cargo_tables=(),
        ),
    )
    deploy_result = RepoPageDeployResult(
        entries=(_unchanged("Template:Item"), _changed("Module:Erenshor/Item")),
    )
    client = RecordingCargoClient({})

    result = recreate_cargo_for_changed_declarations(
        client=client,
        manifest=manifest,
        deploy_result=deploy_result,
        namespaces=(0,),
        assertion="bot",
    )

    assert client.recreate_tables_calls == []
    assert client.recreate_data_calls == []
    assert result.entries == ()


def test_repopulation_batches_using_pages_by_offset() -> None:
    """Data recreation advances the offset once per batch of using-pages."""
    manifest = _manifest(_declaring_entry("Template:Item", "Items"))
    deploy_result = RepoPageDeployResult(entries=(_changed("Template:Item"),))
    using_pages = tuple(f"Page{i}" for i in range(5))
    client = RecordingCargoClient({"Template:Item": using_pages})

    recreate_cargo_for_changed_declarations(
        client=client,
        manifest=manifest,
        deploy_result=deploy_result,
        namespaces=(0,),
        assertion="bot",
        batch_size=2,
    )

    offsets = [call[2] for call in client.recreate_data_calls]
    assert offsets == [0, 2, 4]


def test_table_with_no_using_pages_recreates_schema_only() -> None:
    """A declaration with no transcluding pages rebuilds the schema but skips data recreation."""
    manifest = _manifest(_declaring_entry("Template:Item", "Items"))
    deploy_result = RepoPageDeployResult(entries=(_changed("Template:Item"),))
    client = RecordingCargoClient({"Template:Item": ()})

    recreate_cargo_for_changed_declarations(
        client=client,
        manifest=manifest,
        deploy_result=deploy_result,
        namespaces=(0,),
        assertion="bot",
    )

    assert client.recreate_tables_calls == [("Template:Item", "bot", None)]
    assert client.recreate_data_calls == []
