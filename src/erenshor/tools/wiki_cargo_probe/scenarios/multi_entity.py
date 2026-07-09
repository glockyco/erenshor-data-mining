from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from ..markup import lifecycle_item_call
from ..models import OWNER, TemplatePage, manual_cleanup_urls
from ..queries import (
    multi_entity_key_state_matches,
    query_multi_entity_reverse,
    query_multi_entity_state,
    reverse_page_title_is_ambiguous,
    reverse_rows_match_keys,
)
from .lifecycle import build_lifecycle_probe

if TYPE_CHECKING:
    from ..models import ProbeOperations


@dataclass(frozen=True, slots=True)
class MultiEntityScenario:
    kind: Literal["multi-entity"]
    page_title: str
    template_base: str
    tables: dict[str, str]
    templates: tuple[TemplatePage, ...]
    recreate_templates: tuple[str, ...]
    recreatedata_pairs: tuple[tuple[str, str], ...]
    item_keys: tuple[str, str]
    page_content: str

    @property
    def page_titles(self) -> tuple[str, ...]:
        return (self.page_title,)

    @property
    def template_pages(self) -> tuple[TemplatePage, ...]:
        return self.templates

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self.tables.values())

    def run(self, context: ProbeOperations, poll_seconds: int) -> dict[str, object]:
        del poll_seconds
        result: dict[str, Any] = {
            "kind": self.kind,
            "item_keys": list(self.item_keys),
            "page_title": self.page_title,
            "tables": self.tables,
            "manual_table_cleanup_urls": manual_cleanup_urls(tuple(self.tables.values())),
        }
        try:
            context.create_template_pages(self.templates)
            result["initial_cargorecreatetables"] = [
                context.recreate_tables(template) for template in self.recreate_templates
            ]
            context.create_page(self.page_title, self.page_content)
            result["purged"] = context.purge_pages([self.page_title])
            result["state"] = query_multi_entity_state(context, self)
            result["obtained_from_reverse"] = query_multi_entity_reverse(context, self, "obtained_from")
            result["used_in_reverse"] = query_multi_entity_reverse(context, self, "used_in")
            result["validation_ok"] = (
                all(multi_entity_key_state_matches(result["state"], key) for key in self.item_keys)
                and reverse_rows_match_keys(result["obtained_from_reverse"], self.item_keys)
                and reverse_rows_match_keys(result["used_in_reverse"], self.item_keys)
                and reverse_page_title_is_ambiguous(result["obtained_from_reverse"], len(self.item_keys))
                and reverse_page_title_is_ambiguous(result["used_in_reverse"], len(self.item_keys))
            )
        finally:
            result["page_cleanup"] = context.cleanup_created_pages()
        return result


def build_multi_entity_probe(prefix: str) -> MultiEntityScenario:
    storage = build_lifecycle_probe(prefix + "MultiEntity")
    item_a = prefix + "MultiEntityItemA"
    item_b = prefix + "MultiEntityItemB"
    page_title = "User:" + OWNER + "/CargoStorageProbe/" + prefix + "/MultiEntity"
    page_content = (
        lifecycle_item_call(storage.template_base, item_a, "Multi Entity Item A", ("SharedSource",), ("SharedUse",))
        + "\n"
        + lifecycle_item_call(storage.template_base, item_b, "Multi Entity Item B", ("SharedSource",), ("SharedUse",))
        + "\n"
    )
    return MultiEntityScenario(
        kind="multi-entity",
        page_title=page_title,
        template_base=storage.template_base,
        tables=storage.tables,
        templates=storage.templates,
        recreate_templates=storage.recreate_templates,
        recreatedata_pairs=storage.recreatedata_pairs,
        item_keys=(item_a, item_b),
        page_content=page_content,
    )
