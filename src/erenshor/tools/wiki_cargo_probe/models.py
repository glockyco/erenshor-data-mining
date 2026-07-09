from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

OWNER = "WoWMuch"
REQUIRED_RIGHTS = frozenset({"edit", "createpage", "delete", "recreatecargodata"})
MANUAL_DELETE_BASE = "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/"

StandardKind = Literal["direct", "nested", "lua-nested"]
ScenarioKind = Literal[
    "direct",
    "nested",
    "lua-nested",
    "lifecycle",
    "multi-entity",
    "recreate-batching",
    "replacement-table",
]


@dataclass(frozen=True, slots=True)
class TemplatePage:
    title: str
    content: str


class CargoQuerier(Protocol):
    def query_cargo_table(
        self, *, tables: str, fields: str, where: str | None = None, limit: int = 50
    ) -> dict[str, Any]: ...


class ProbeOperations(CargoQuerier, Protocol):
    def create_page(self, title: str, content: str) -> None: ...

    def create_template_pages(self, templates: tuple[TemplatePage, ...]) -> None: ...

    def edit_existing_page(self, title: str, content: str, summary: str) -> None: ...

    def forget_created_page(self, title: str) -> None: ...

    def cleanup_created_pages(self) -> list[dict[str, Any]]: ...

    def purge_pages(self, titles: tuple[str, ...] | list[str]) -> tuple[str, ...]: ...

    def purge_pages_in_batches(self, titles: tuple[str, ...], batch_size: int = 50) -> list[tuple[str, ...]]: ...

    def recreate_tables(self, template: str, *, create_replacement: bool = False) -> dict[str, Any]: ...

    def recreate_data(self, template: str, table: str, *, replace_old_rows: bool = True) -> dict[str, Any]: ...

    def parse_page_html(self, page_title: str) -> dict[str, Any]: ...

    def delete_page(self, title: str) -> dict[str, Any]: ...


class ProbeScenario(Protocol):
    @property
    def kind(self) -> ScenarioKind: ...

    @property
    def page_titles(self) -> tuple[str, ...]: ...

    @property
    def template_pages(self) -> tuple[TemplatePage, ...]: ...

    @property
    def table_names(self) -> tuple[str, ...]: ...

    def run(self, context: ProbeOperations, poll_seconds: int) -> dict[str, object]: ...


def manual_cleanup_urls(tables: Sequence[str]) -> list[str]:
    return [MANUAL_DELETE_BASE + table for table in tables]
