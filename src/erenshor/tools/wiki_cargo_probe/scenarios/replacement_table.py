from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from ..models import OWNER, TemplatePage, manual_cleanup_urls
from ..queries import query_lifecycle_count, query_replacement_probe_row, replacement_row_matches

if TYPE_CHECKING:
    from ..models import ProbeOperations


@dataclass(frozen=True, slots=True)
class ReplacementTableScenario:
    kind: Literal["replacement-table"]
    key: str
    page_title: str
    template_name: str
    table: str
    replacement_table: str
    template: TemplatePage
    page_content: str

    @property
    def page_titles(self) -> tuple[str, ...]:
        return (self.page_title,)

    @property
    def template_pages(self) -> tuple[TemplatePage, ...]:
        return (self.template,)

    @property
    def table_names(self) -> tuple[str, ...]:
        return (self.table, self.replacement_table)

    def run(self, context: ProbeOperations, poll_seconds: int) -> dict[str, object]:
        del poll_seconds
        result: dict[str, Any] = {
            "kind": self.kind,
            "key": self.key,
            "page_title": self.page_title,
            "template_name": self.template_name,
            "table": self.table,
            "replacement_table": self.replacement_table,
            "manual_table_cleanup_urls": manual_cleanup_urls(self.table_names),
            "switch_in_contract": "Special:CargoTables UI after replacement population completes",
        }
        try:
            context.create_page(self.template.title, self.template.content)
            result["initial_cargorecreatetables"] = context.recreate_tables(self.template_name)
            context.create_page(self.page_title, self.page_content)
            result["purged"] = context.purge_pages([self.page_title])
            result["initial_original_count"] = query_lifecycle_count(context, self.table)
            result["initial_original_row"] = query_replacement_probe_row(context, self.table, self.key)
            result["create_replacement"] = context.recreate_tables(self.template_name, create_replacement=True)
            result["replacement_count"] = query_lifecycle_count(context, self.replacement_table)
            result["replacement_row"] = query_replacement_probe_row(context, self.replacement_table, self.key)
            result["replacement_queryable_before_switch"] = replacement_row_matches(result["replacement_row"], self.key)
            result["replacement_rows_hidden_before_switch"] = (
                result["replacement_count"].get("ok")
                and result["replacement_count"].get("count") == 0
                and result["replacement_row"].get("ok")
                and result["replacement_row"].get("rows") == []
            )
            result["replacement_population_verification"] = (
                "Replacement table rows are not API-queryable before Special:CargoTables switch-in"
            )
            result["original_after_replacement_count"] = query_lifecycle_count(context, self.table)
            result["original_after_replacement_row"] = query_replacement_probe_row(context, self.table, self.key)
            result["validation_ok"] = (
                result["initial_original_count"].get("ok")
                and result["initial_original_count"].get("count") == 1
                and replacement_row_matches(result["initial_original_row"], self.key)
                and result["create_replacement"].get("ok")
                and result["create_replacement"].get("response", {}).get("success") is True
                and result["replacement_rows_hidden_before_switch"]
                and result["original_after_replacement_count"].get("ok")
                and result["original_after_replacement_count"].get("count") == 1
                and replacement_row_matches(result["original_after_replacement_row"], self.key)
            )
        finally:
            result["page_cleanup"] = context.cleanup_created_pages()
        return result


def build_replacement_table_probe(prefix: str) -> ReplacementTableScenario:
    key = prefix + "ReplacementKey"
    table = prefix + "ReplacementItems"
    template_name = "CargoStorageProbe/" + prefix + "/Replacement"
    template_title = "Template:" + template_name
    page_title = "User:" + OWNER + "/CargoStorageProbe/" + prefix + "/Replacement"
    template_content = (
        "<includeonly>"
        + "{{#cargo_store:_table="
        + table
        + "|ProbeKey={{{key|}}}|ProbeValue=Original}}"
        + "</includeonly><noinclude>"
        + "{{#cargo_declare:_table="
        + table
        + "|ProbeKey=String|ProbeValue=String}}"
        + "Temporary Cargo replacement-table probe."
        + "</noinclude>"
    )
    return ReplacementTableScenario(
        kind="replacement-table",
        key=key,
        page_title=page_title,
        template_name=template_name,
        table=table,
        replacement_table=table + "__NEXT",
        template=TemplatePage(template_title, template_content),
        page_content="{{" + template_name + "|key=" + key + "}}\n",
    )
