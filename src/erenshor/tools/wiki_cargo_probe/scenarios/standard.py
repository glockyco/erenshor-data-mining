from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..markup import declare_probe_table, store_probe_row
from ..models import StandardKind, TemplatePage, manual_cleanup_urls
from ..queries import query_all, standard_candidate_validation, wait_for_rows

if TYPE_CHECKING:
    from ..models import ProbeOperations


@dataclass(frozen=True, slots=True)
class StandardProbeScenario:
    kind: StandardKind
    key: str
    page_title: str
    template_base: str
    tables: dict[str, str]
    expected_counts: dict[str, int]
    templates: tuple[TemplatePage, ...]
    recreate_templates: tuple[str, ...]
    recreatedata_pairs: tuple[tuple[str, str], ...]

    @property
    def page_titles(self) -> tuple[str, ...]:
        return (self.page_title,)

    @property
    def template_pages(self) -> tuple[TemplatePage, ...]:
        return self.templates

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self.tables.values())

    @property
    def transclusion(self) -> str:
        return "{{" + self.template_base + "Main|key=" + self.key + "}}\n"

    def run(self, context: ProbeOperations, poll_seconds: int) -> dict[str, object]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "key": self.key,
            "page_title": self.page_title,
            "tables": self.tables,
            "expected_counts": self.expected_counts,
            "manual_table_cleanup_urls": manual_cleanup_urls(tuple(self.tables.values())),
        }
        try:
            context.create_template_pages(self.templates)
            result["initial_cargorecreatetables"] = [
                context.recreate_tables(template) for template in self.recreate_templates
            ]
            context.create_page(self.page_title, self.transclusion)
            result["purged"] = context.purge_pages([self.page_title])
            result["initial_queries"] = query_all(context, self)
            result["rendered_page"] = context.parse_page_html(self.page_title)
            result["post_page_cargorecreatetables"] = [
                context.recreate_tables(template) for template in self.recreate_templates
            ]
            result["queries_after_cargorecreatetables"] = query_all(context, self)
            result["wait_after_cargorecreatetables"] = wait_for_rows(context, self, poll_seconds)
            result["cargorecreatedata"] = [
                context.recreate_data(template, table) for template, table in self.recreatedata_pairs
            ]
            result["queries_after_cargorecreatedata"] = query_all(context, self)
            result["validation_ok"] = standard_candidate_validation(result, self)
        finally:
            result["page_cleanup"] = context.cleanup_created_pages()
        return result


def build_direct_probe(prefix: str) -> StandardProbeScenario:
    key = prefix + "DirectKey"
    tables = {"A": prefix + "DirectA", "B": prefix + "DirectB", "C": prefix + "DirectC"}
    template_base = "CargoStorageProbe/" + prefix + "/Direct"
    main_title = "Template:" + template_base + "Main"
    b_title = "Template:" + template_base + "BDeclare"
    c_title = "Template:" + template_base + "CDeclare"
    page_title = "User:WoWMuch/CargoStorageProbe/" + prefix + "/Direct"

    main = (
        "<includeonly>"
        + store_probe_row(tables["A"], "A", 11, "yes")
        + store_probe_row(tables["B"], "B", 21, "yes")
        + store_probe_row(tables["C"], "C", 31, "no")
        + "</includeonly><noinclude>"
        + declare_probe_table(tables["A"])
        + "{{#cargo_attach:_table="
        + tables["B"]
        + "}}"
        + "{{#cargo_attach:_table="
        + tables["C"]
        + "}}"
        + "Temporary direct multi-attach Cargo storage probe."
        + "</noinclude>"
    )
    b_decl = "<includeonly></includeonly><noinclude>" + declare_probe_table(tables["B"]) + "Temporary.</noinclude>"
    c_decl = "<includeonly></includeonly><noinclude>" + declare_probe_table(tables["C"]) + "Temporary.</noinclude>"

    return StandardProbeScenario(
        kind="direct",
        key=key,
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        expected_counts={"A": 1, "B": 1, "C": 1},
        templates=(TemplatePage(main_title, main), TemplatePage(b_title, b_decl), TemplatePage(c_title, c_decl)),
        recreate_templates=(template_base + "BDeclare", template_base + "CDeclare", template_base + "Main"),
        recreatedata_pairs=(
            (template_base + "Main", tables["A"]),
            (template_base + "Main", tables["B"]),
            (template_base + "Main", tables["C"]),
        ),
    )


def build_nested_probe(prefix: str) -> StandardProbeScenario:
    key = prefix + "NestedKey"
    tables = {"A": prefix + "NestedA", "B": prefix + "NestedB", "C": prefix + "NestedC"}
    template_base = "CargoStorageProbe/" + prefix + "/Nested"
    main_title = "Template:" + template_base + "Main"
    b_title = "Template:" + template_base + "BStore"
    c_title = "Template:" + template_base + "CStore"
    page_title = "User:WoWMuch/CargoStorageProbe/" + prefix + "/Nested"

    main = (
        "<includeonly>"
        + store_probe_row(tables["A"], "A", 11, "yes")
        + "{{"
        + template_base
        + "BStore|key={{{key|}}}}}"
        + "{{"
        + template_base
        + "CStore|key={{{key|}}}}}"
        + "</includeonly><noinclude>"
        + declare_probe_table(tables["A"])
        + "Temporary nested Cargo storage probe."
        + "</noinclude>"
    )
    b_store = (
        "<includeonly>"
        + store_probe_row(tables["B"], "B", 21, "yes")
        + "</includeonly><noinclude>"
        + declare_probe_table(tables["B"])
        + "Temporary.</noinclude>"
    )
    c_store = (
        "<includeonly>"
        + store_probe_row(tables["C"], "C", 31, "no")
        + "</includeonly><noinclude>"
        + declare_probe_table(tables["C"])
        + "Temporary.</noinclude>"
    )

    return StandardProbeScenario(
        kind="nested",
        key=key,
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        expected_counts={"A": 1, "B": 1, "C": 1},
        templates=(TemplatePage(main_title, main), TemplatePage(b_title, b_store), TemplatePage(c_title, c_store)),
        recreate_templates=(template_base + "Main", template_base + "BStore", template_base + "CStore"),
        recreatedata_pairs=(
            (template_base + "Main", tables["A"]),
            (template_base + "BStore", tables["B"]),
            (template_base + "CStore", tables["C"]),
        ),
    )


def build_lua_nested_probe(prefix: str) -> StandardProbeScenario:
    key = prefix + "LuaNestedKey"
    tables = {"A": prefix + "LuaNestedA", "B": prefix + "LuaNestedB", "C": prefix + "LuaNestedC"}
    template_base = "CargoStorageProbe/" + prefix + "/LuaNested"
    module_title = "Module:CargoStorageProbe/" + prefix
    main_title = "Template:" + template_base + "Main"
    b_title = "Template:" + template_base + "BStore"
    c_title = "Template:" + template_base + "CStore"
    page_title = "User:WoWMuch/CargoStorageProbe/" + prefix + "/LuaNested"

    module = (
        "local p = {}\n"
        + "local tables = { A = '"
        + tables["A"]
        + "', B = '"
        + tables["B"]
        + "', C = '"
        + tables["C"]
        + "' }\n"
        + "local function cast(value)\n"
        + "  if value == nil then return nil end\n"
        + "  if type(value) == 'boolean' then return value and 'yes' or 'no' end\n"
        + "  return tostring(value)\n"
        + "end\n"
        + "local function store(frame, tableName, value, flag, number)\n"
        + "  return frame:callParserFunction('#cargo_store:', {\n"
        + "    _table = tableName,\n"
        + "    ProbeKey = frame.args.key or '',\n"
        + "    ProbeValue = value,\n"
        + "    ProbeFlag = cast(flag),\n"
        + "    ProbeNumber = cast(number),\n"
        + "  })\n"
        + "end\n"
        + "function p.storeA(frame)\n"
        + "  return store(frame, tables.A, 'A', true, 11)\n"
        + "end\n"
        + "function p.storeB(frame)\n"
        + "  return store(frame, tables.B, 'B1', true, 21) .. store(frame, tables.B, 'B2', false, 22)\n"
        + "end\n"
        + "function p.storeC(frame)\n"
        + "  return store(frame, tables.C, 'C', false, 31)\n"
        + "end\n"
        + "return p\n"
    )
    main = (
        "<includeonly>"
        + "{{#invoke:CargoStorageProbe/"
        + prefix
        + "|storeA|key={{{key|}}}}}"
        + "{{"
        + template_base
        + "BStore|key={{{key|}}}}}"
        + "{{"
        + template_base
        + "CStore|key={{{key|}}}}}"
        + "</includeonly><noinclude>"
        + declare_probe_table(tables["A"])
        + "Temporary Lua nested Cargo storage probe."
        + "</noinclude>"
    )
    b_store = (
        "<includeonly>{{#invoke:CargoStorageProbe/"
        + prefix
        + "|storeB|key={{{key|}}}}}</includeonly><noinclude>"
        + declare_probe_table(tables["B"])
        + "Temporary.</noinclude>"
    )
    c_store = (
        "<includeonly>{{#invoke:CargoStorageProbe/"
        + prefix
        + "|storeC|key={{{key|}}}}}</includeonly><noinclude>"
        + declare_probe_table(tables["C"])
        + "Temporary.</noinclude>"
    )

    return StandardProbeScenario(
        kind="lua-nested",
        key=key,
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        expected_counts={"A": 1, "B": 2, "C": 1},
        templates=(
            TemplatePage(module_title, module),
            TemplatePage(main_title, main),
            TemplatePage(b_title, b_store),
            TemplatePage(c_title, c_store),
        ),
        recreate_templates=(template_base + "Main", template_base + "BStore", template_base + "CStore"),
        recreatedata_pairs=(
            (template_base + "Main", tables["A"]),
            (template_base + "BStore", tables["B"]),
            (template_base + "CStore", tables["C"]),
        ),
    )
