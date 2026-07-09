from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from ..markup import declare_lifecycle_table, lifecycle_item_call
from ..models import OWNER, TemplatePage, manual_cleanup_urls
from ..queries import lifecycle_state_matches, query_lifecycle_state, wait_for_lifecycle_state

if TYPE_CHECKING:
    from ..models import ProbeOperations


@dataclass(frozen=True, slots=True)
class LifecycleScenario:
    kind: Literal["lifecycle"]
    page_title: str
    template_base: str
    tables: dict[str, str]
    templates: tuple[TemplatePage, ...]
    recreate_templates: tuple[str, ...]
    recreatedata_pairs: tuple[tuple[str, str], ...]
    item_key: str
    removed_key: str
    initial_content: str
    reduced_content: str
    removed_content: str

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
        result: dict[str, Any] = {
            "kind": self.kind,
            "item_key": self.item_key,
            "removed_key": self.removed_key,
            "page_title": self.page_title,
            "tables": self.tables,
            "manual_table_cleanup_urls": manual_cleanup_urls(tuple(self.tables.values())),
        }
        try:
            context.create_template_pages(self.templates)
            result["initial_cargorecreatetables"] = [
                context.recreate_tables(template) for template in self.recreate_templates
            ]
            context.create_page(self.page_title, self.initial_content)
            result["initial_purged"] = context.purge_pages([self.page_title])
            result["initial_state"] = wait_for_lifecycle_state(
                context,
                self,
                poll_seconds,
                item_sources=("SourceA1", "SourceA2", "SourceA3"),
                item_uses=("UseA1",),
                removed_sources=("SourceB1",),
                removed_uses=("UseB1",),
            )
            context.edit_existing_page(
                self.page_title,
                self.reduced_content,
                "Reduce temporary Cargo lifecycle probe rows",
            )
            result["reduced_purged"] = context.purge_pages([self.page_title])
            result["reduced_state"] = wait_for_lifecycle_state(
                context,
                self,
                poll_seconds,
                item_sources=("SourceA1",),
                item_uses=(),
                removed_sources=("SourceB1",),
                removed_uses=("UseB1",),
            )
            context.edit_existing_page(
                self.page_title,
                self.removed_content,
                "Remove one temporary Cargo lifecycle probe item",
            )
            result["removed_purged"] = context.purge_pages([self.page_title])
            result["removed_item_state"] = wait_for_lifecycle_state(
                context,
                self,
                poll_seconds,
                item_sources=("SourceA1",),
                item_uses=(),
                removed_sources=(),
                removed_uses=(),
                removed_present=False,
            )
            result["delete_page"] = context.delete_page(self.page_title)
            if result["delete_page"].get("ok"):
                context.forget_created_page(self.page_title)
            result["after_delete_state"] = query_lifecycle_state(context, self)
            result["after_delete_rows_removed"] = lifecycle_state_matches(
                result["after_delete_state"],
                self,
                item_sources=(),
                item_uses=(),
                removed_sources=(),
                removed_uses=(),
                removed_present=False,
                item_present=False,
            )
            result["validation_ok"] = (
                result["initial_state"].get("matches")
                and result["reduced_state"].get("matches")
                and result["removed_item_state"].get("matches")
                and result["delete_page"].get("ok")
                and result["after_delete_rows_removed"]
            )
        finally:
            result["page_cleanup"] = context.cleanup_created_pages()
        return result


def build_lifecycle_probe(prefix: str) -> LifecycleScenario:
    item_key = prefix + "LifecycleItemA"
    removed_key = prefix + "LifecycleItemB"
    tables = {
        "Items": prefix + "LifecycleItems",
        "ObtainedFrom": prefix + "LifecycleObtainedFrom",
        "UsedIn": prefix + "LifecycleUsedIn",
    }
    template_base = "CargoStorageProbe/" + prefix + "/Lifecycle"
    module_name = "CargoStorageProbe/" + prefix + "/Lifecycle"
    module_title = "Module:" + module_name
    main_title = "Template:" + template_base + "Main"
    obtained_title = "Template:" + template_base + "ObtainedFromStore"
    used_title = "Template:" + template_base + "UsedInStore"
    page_title = "User:" + OWNER + "/CargoStorageProbe/" + prefix + "/Lifecycle"

    module = (
        "local p = {}\n"
        + "local tables = { Items = '"
        + tables["Items"]
        + "', ObtainedFrom = '"
        + tables["ObtainedFrom"]
        + "', UsedIn = '"
        + tables["UsedIn"]
        + "' }\n"
        + "local function arg(frame, name)\n"
        + "  return frame.args[name] or ''\n"
        + "end\n"
        + "local function store(frame, values)\n"
        + "  return frame:callParserFunction('#cargo_store:', values)\n"
        + "end\n"
        + "function p.storeItem(frame)\n"
        + "  return store(frame, {\n"
        + "    _table = tables.Items,\n"
        + "    StableKey = arg(frame, 'stablekey'),\n"
        + "    DisplayName = arg(frame, 'name'),\n"
        + "  })\n"
        + "end\n"
        + "function p.storeObtainedFrom(frame)\n"
        + "  local output = ''\n"
        + "  for index = 1, 10 do\n"
        + "    local source = arg(frame, 'source' .. tostring(index))\n"
        + "    if source ~= '' then\n"
        + "      output = output .. store(frame, {\n"
        + "        _table = tables.ObtainedFrom,\n"
        + "        ItemKey = arg(frame, 'itemkey'),\n"
        + "        SourceKey = source,\n"
        + "        SourceIndex = tostring(index),\n"
        + "      })\n"
        + "    end\n"
        + "  end\n"
        + "  return output\n"
        + "end\n"
        + "function p.storeUsedIn(frame)\n"
        + "  local output = ''\n"
        + "  for index = 1, 10 do\n"
        + "    local use = arg(frame, 'use' .. tostring(index))\n"
        + "    if use ~= '' then\n"
        + "      output = output .. store(frame, {\n"
        + "        _table = tables.UsedIn,\n"
        + "        ItemKey = arg(frame, 'itemkey'),\n"
        + "        UseKey = use,\n"
        + "        UseIndex = tostring(index),\n"
        + "      })\n"
        + "    end\n"
        + "  end\n"
        + "  return output\n"
        + "end\n"
        + "return p\n"
    )
    main = (
        "<includeonly>"
        + "{{#invoke:"
        + module_name
        + "|storeItem|stablekey={{{stablekey|}}}|name={{{name|}}}}}"
        + "{{"
        + template_base
        + "ObtainedFromStore|itemkey={{{stablekey|}}}|source1={{{source1|}}}"
        + "|source2={{{source2|}}}|source3={{{source3|}}}}}"
        + "{{"
        + template_base
        + "UsedInStore|itemkey={{{stablekey|}}}|use1={{{use1|}}}|use2={{{use2|}}}|use3={{{use3|}}}}}"
        + "</includeonly><noinclude>"
        + declare_lifecycle_table(tables["Items"], "StableKey=String|DisplayName=String")
        + "Temporary Cargo lifecycle storage probe."
        + "</noinclude>"
    )
    obtained_store = (
        "<includeonly>{{#invoke:"
        + module_name
        + "|storeObtainedFrom|itemkey={{{itemkey|}}}|source1={{{source1|}}}"
        + "|source2={{{source2|}}}|source3={{{source3|}}}}}</includeonly><noinclude>"
        + declare_lifecycle_table(tables["ObtainedFrom"], "ItemKey=String|SourceKey=String|SourceIndex=Integer")
        + "Temporary.</noinclude>"
    )
    used_store = (
        "<includeonly>{{#invoke:"
        + module_name
        + "|storeUsedIn|itemkey={{{itemkey|}}}|use1={{{use1|}}}"
        + "|use2={{{use2|}}}|use3={{{use3|}}}}}</includeonly><noinclude>"
        + declare_lifecycle_table(tables["UsedIn"], "ItemKey=String|UseKey=String|UseIndex=Integer")
        + "Temporary.</noinclude>"
    )
    initial_content = (
        lifecycle_item_call(
            template_base,
            item_key,
            "Lifecycle Item A",
            ("SourceA1", "SourceA2", "SourceA3"),
            ("UseA1",),
        )
        + "\n"
        + lifecycle_item_call(template_base, removed_key, "Lifecycle Item B", ("SourceB1",), ("UseB1",))
        + "\n"
    )
    reduced_content = (
        lifecycle_item_call(template_base, item_key, "Lifecycle Item A", ("SourceA1",), ())
        + "\n"
        + lifecycle_item_call(template_base, removed_key, "Lifecycle Item B", ("SourceB1",), ("UseB1",))
        + "\n"
    )
    removed_content = lifecycle_item_call(template_base, item_key, "Lifecycle Item A", ("SourceA1",), ()) + "\n"

    return LifecycleScenario(
        kind="lifecycle",
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        templates=(
            TemplatePage(module_title, module),
            TemplatePage(main_title, main),
            TemplatePage(obtained_title, obtained_store),
            TemplatePage(used_title, used_store),
        ),
        recreate_templates=(
            template_base + "Main",
            template_base + "ObtainedFromStore",
            template_base + "UsedInStore",
        ),
        recreatedata_pairs=(
            (template_base + "Main", tables["Items"]),
            (template_base + "ObtainedFromStore", tables["ObtainedFrom"]),
            (template_base + "UsedInStore", tables["UsedIn"]),
        ),
        item_key=item_key,
        removed_key=removed_key,
        initial_content=initial_content,
        reduced_content=reduced_content,
        removed_content=removed_content,
    )
