"""Cargo table recreation for changed declaration deploys.

When a repo-owned template whose ``#cargo_declare`` changed is deployed, the
physical Cargo table no longer matches the declaration. This pass recreates the
schema for each such template and repopulates its row data from the pages that
transclude it. A forced purge does not re-store Cargo rows, so the data must be
recreated explicitly after the schema is rebuilt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from erenshor.application.wiki_deploy.manifest import RepoWikiPageManifest
    from erenshor.application.wiki_deploy.pages import RepoPageDeployResult

EditAssertion = Literal["user", "bot"]

# Cargo recreates row data one batch of using-pages at a time. Its default batch
# size is 500; mirroring that keeps the offset advance aligned with the server.
DEFAULT_CARGO_BATCH_SIZE = 500


class CargoRecreateClient(Protocol):
    """MediaWiki operations required to recreate a Cargo table and its data."""

    def recreate_cargo_tables(
        self,
        template_title: str,
        create_replacement: bool = False,
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> None: ...

    def get_embeddedin_pages(
        self,
        title: str,
        namespaces: Sequence[int] = (0,),
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> tuple[str, ...]: ...

    def recreate_cargo_data(
        self,
        template_title: str,
        table: str,
        offset: int = 0,
        replace_old_rows: bool = True,
        assertion: EditAssertion | None = None,
        assert_user: str | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CargoRecreateResultEntry:
    """Recreation outcome for one changed declaring template."""

    template_title: str
    tables: tuple[str, ...]
    using_page_count: int


@dataclass(frozen=True, slots=True)
class CargoRecreateResult:
    """Cargo tables recreated during a deploy or rollback."""

    entries: tuple[CargoRecreateResultEntry, ...]


def recreate_cargo_for_changed_declarations(
    *,
    client: CargoRecreateClient,
    manifest: RepoWikiPageManifest,
    deploy_result: RepoPageDeployResult,
    namespaces: tuple[int, ...],
    assertion: EditAssertion,
    assert_user: str | None = None,
    batch_size: int = DEFAULT_CARGO_BATCH_SIZE,
) -> CargoRecreateResult:
    """Recreate Cargo tables for every changed Cargo-declaring template.

    For each such template the schema is recreated, then the row data is
    recreated in batches over the pages that transclude it. Templates that did
    not change, or that declare no Cargo table, are left untouched.
    """
    changed_titles = {entry.title for entry in deploy_result.entries if entry.status == "changed"}

    result_entries: list[CargoRecreateResultEntry] = []
    for entry in manifest.entries:
        if entry.title not in changed_titles or not entry.declares_cargo_table:
            continue

        client.recreate_cargo_tables(entry.title, assertion=assertion, assert_user=assert_user)

        using_pages = client.get_embeddedin_pages(
            entry.title,
            namespaces=namespaces,
            assertion=assertion,
            assert_user=assert_user,
        )
        for table in entry.cargo_tables:
            for offset in range(0, len(using_pages), batch_size):
                client.recreate_cargo_data(
                    entry.title,
                    table,
                    offset=offset,
                    assertion=assertion,
                    assert_user=assert_user,
                )

        result_entries.append(
            CargoRecreateResultEntry(
                template_title=entry.title,
                tables=entry.cargo_tables,
                using_page_count=len(using_pages),
            )
        )

    return CargoRecreateResult(entries=tuple(result_entries))
