from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from .operations import ProbeRunContext

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


class ProbeScenario(Protocol):
    @property
    def kind(self) -> ScenarioKind: ...

    @property
    def page_titles(self) -> tuple[str, ...]: ...

    @property
    def template_pages(self) -> tuple[TemplatePage, ...]: ...

    @property
    def table_names(self) -> tuple[str, ...]: ...

    def run(self, context: ProbeRunContext, poll_seconds: int) -> dict[str, object]: ...


def manual_cleanup_urls(tables: Sequence[str]) -> list[str]:
    return [MANUAL_DELETE_BASE + table for table in tables]
