#!/usr/bin/env python3
"""Probe live wiki.gg Cargo storage and recreate behavior.

This tool intentionally defaults to a dry run. Pass ``--live`` to create temporary
sandbox templates/pages on the configured MediaWiki target. Live runs delete the
sandbox pages they create, but Cargo tables require manual admin cleanup through
Special:CargoTables / Special:DeleteCargoTable.

Usage:
    uv run python src/tools/wiki_cargo_storage_probe.py
    uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate lua-nested
    uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate all --prefix Probe20260709
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from erenshor.infrastructure.config.loader import load_config
from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient

OWNER = "WoWMuch"
REQUIRED_RIGHTS = frozenset({"edit", "createpage", "delete", "recreatecargodata"})
MANUAL_DELETE_BASE = "https://erenshor.wiki.gg/wiki/Special:DeleteCargoTable/"

CandidateKind = Literal["direct", "nested", "lua-nested", "lifecycle"]


@dataclass(frozen=True, slots=True)
class TemplatePage:
    title: str
    content: str


@dataclass(frozen=True, slots=True)
class ProbeCandidate:
    kind: CandidateKind
    key: str
    page_title: str
    template_base: str
    tables: dict[str, str]
    expected_counts: dict[str, int]
    templates: tuple[TemplatePage, ...]
    recreate_templates: tuple[str, ...]
    recreatedata_pairs: tuple[tuple[str, str], ...]

    @property
    def transclusion(self) -> str:
        return "{{" + self.template_base + "Main|key=" + self.key + "}}\n"


@dataclass(frozen=True, slots=True)
class LifecycleCandidate:
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


type Candidate = ProbeCandidate | LifecycleCandidate


def _store(table_placeholder: str, value: str, number: int = 1, flag: str = "yes") -> str:
    return (
        "{{#cargo_store:_table="
        + table_placeholder
        + "|ProbeKey={{{key|}}}|ProbeValue="
        + value
        + "|ProbeFlag="
        + flag
        + "|ProbeNumber="
        + str(number)
        + "}}"
    )


def _declare(table_placeholder: str) -> str:
    return (
        "{{#cargo_declare:_table="
        + table_placeholder
        + "|ProbeKey=String|ProbeValue=String|ProbeFlag=Boolean|ProbeNumber=Integer}}"
    )


def _fill_tables(content: str, tables: dict[str, str]) -> str:
    for name, table in tables.items():
        content = content.replace("__" + name + "__", table)
    return content


def build_direct_candidate(prefix: str) -> ProbeCandidate:
    key = prefix + "DirectKey"
    tables = {"A": prefix + "DirectA", "B": prefix + "DirectB", "C": prefix + "DirectC"}
    template_base = "CargoStorageProbe/" + prefix + "/Direct"
    main_title = "Template:" + template_base + "Main"
    b_title = "Template:" + template_base + "BDeclare"
    c_title = "Template:" + template_base + "CDeclare"
    page_title = "User:" + OWNER + "/CargoStorageProbe/" + prefix + "/Direct"

    main = (
        "<includeonly>"
        + _store("__A__", "A", 11, "yes")
        + _store("__B__", "B", 21, "yes")
        + _store("__C__", "C", 31, "no")
        + "</includeonly><noinclude>"
        + _declare("__A__")
        + "{{#cargo_attach:_table=__B__}}"
        + "{{#cargo_attach:_table=__C__}}"
        + "Temporary direct multi-attach Cargo storage probe."
        + "</noinclude>"
    )
    b_decl = "<includeonly></includeonly><noinclude>" + _declare("__B__") + "Temporary.</noinclude>"
    c_decl = "<includeonly></includeonly><noinclude>" + _declare("__C__") + "Temporary.</noinclude>"

    return ProbeCandidate(
        kind="direct",
        key=key,
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        expected_counts={"A": 1, "B": 1, "C": 1},
        templates=(
            TemplatePage(main_title, _fill_tables(main, tables)),
            TemplatePage(b_title, _fill_tables(b_decl, tables)),
            TemplatePage(c_title, _fill_tables(c_decl, tables)),
        ),
        recreate_templates=(template_base + "BDeclare", template_base + "CDeclare", template_base + "Main"),
        recreatedata_pairs=(
            (template_base + "Main", tables["A"]),
            (template_base + "Main", tables["B"]),
            (template_base + "Main", tables["C"]),
        ),
    )


def build_nested_candidate(prefix: str) -> ProbeCandidate:
    key = prefix + "NestedKey"
    tables = {"A": prefix + "NestedA", "B": prefix + "NestedB", "C": prefix + "NestedC"}
    template_base = "CargoStorageProbe/" + prefix + "/Nested"
    main_title = "Template:" + template_base + "Main"
    b_title = "Template:" + template_base + "BStore"
    c_title = "Template:" + template_base + "CStore"
    page_title = "User:" + OWNER + "/CargoStorageProbe/" + prefix + "/Nested"

    main = (
        "<includeonly>"
        + _store("__A__", "A", 11, "yes")
        + "{{"
        + template_base
        + "BStore|key={{{key|}}}}}"
        + "{{"
        + template_base
        + "CStore|key={{{key|}}}}}"
        + "</includeonly><noinclude>"
        + _declare("__A__")
        + "Temporary nested Cargo storage probe."
        + "</noinclude>"
    )
    b_store = (
        "<includeonly>"
        + _store("__B__", "B", 21, "yes")
        + "</includeonly><noinclude>"
        + _declare("__B__")
        + "Temporary.</noinclude>"
    )
    c_store = (
        "<includeonly>"
        + _store("__C__", "C", 31, "no")
        + "</includeonly><noinclude>"
        + _declare("__C__")
        + "Temporary.</noinclude>"
    )

    return ProbeCandidate(
        kind="nested",
        key=key,
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        expected_counts={"A": 1, "B": 1, "C": 1},
        templates=(
            TemplatePage(main_title, _fill_tables(main, tables)),
            TemplatePage(b_title, _fill_tables(b_store, tables)),
            TemplatePage(c_title, _fill_tables(c_store, tables)),
        ),
        recreate_templates=(template_base + "Main", template_base + "BStore", template_base + "CStore"),
        recreatedata_pairs=(
            (template_base + "Main", tables["A"]),
            (template_base + "BStore", tables["B"]),
            (template_base + "CStore", tables["C"]),
        ),
    )


def build_lua_nested_candidate(prefix: str) -> ProbeCandidate:
    key = prefix + "LuaNestedKey"
    tables = {"A": prefix + "LuaNestedA", "B": prefix + "LuaNestedB", "C": prefix + "LuaNestedC"}
    template_base = "CargoStorageProbe/" + prefix + "/LuaNested"
    module_title = "Module:CargoStorageProbe/" + prefix
    main_title = "Template:" + template_base + "Main"
    b_title = "Template:" + template_base + "BStore"
    c_title = "Template:" + template_base + "CStore"
    page_title = "User:" + OWNER + "/CargoStorageProbe/" + prefix + "/LuaNested"

    module = (
        "local p = {}\n"
        + "local tables = { A = '__A__', B = '__B__', C = '__C__' }\n"
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
        + _declare("__A__")
        + "Temporary Lua nested Cargo storage probe."
        + "</noinclude>"
    )
    b_store = (
        "<includeonly>{{#invoke:CargoStorageProbe/"
        + prefix
        + "|storeB|key={{{key|}}}}}</includeonly><noinclude>"
        + _declare("__B__")
        + "Temporary.</noinclude>"
    )
    c_store = (
        "<includeonly>{{#invoke:CargoStorageProbe/"
        + prefix
        + "|storeC|key={{{key|}}}}}</includeonly><noinclude>"
        + _declare("__C__")
        + "Temporary.</noinclude>"
    )

    return ProbeCandidate(
        kind="lua-nested",
        key=key,
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        expected_counts={"A": 1, "B": 2, "C": 1},
        templates=(
            TemplatePage(module_title, _fill_tables(module, tables)),
            TemplatePage(main_title, _fill_tables(main, tables)),
            TemplatePage(b_title, _fill_tables(b_store, tables)),
            TemplatePage(c_title, _fill_tables(c_store, tables)),
        ),
        recreate_templates=(template_base + "Main", template_base + "BStore", template_base + "CStore"),
        recreatedata_pairs=(
            (template_base + "Main", tables["A"]),
            (template_base + "BStore", tables["B"]),
            (template_base + "CStore", tables["C"]),
        ),
    )


def _lifecycle_declare_items(table_placeholder: str) -> str:
    return "{{#cargo_declare:_table=" + table_placeholder + "|StableKey=String|DisplayName=String}}"


def _lifecycle_declare_obtained_from(table_placeholder: str) -> str:
    return "{{#cargo_declare:_table=" + table_placeholder + "|ItemKey=String|SourceKey=String|SourceIndex=Integer}}"


def _lifecycle_declare_used_in(table_placeholder: str) -> str:
    return "{{#cargo_declare:_table=" + table_placeholder + "|ItemKey=String|UseKey=String|UseIndex=Integer}}"


def _lifecycle_item_call(
    template_base: str,
    stable_key: str,
    name: str,
    sources: tuple[str, ...],
    uses: tuple[str, ...],
) -> str:
    fields = [
        "{{" + template_base + "Main",
        "|stablekey=" + stable_key,
        "|name=" + name,
    ]
    fields.extend("|source" + str(index) + "=" + source for index, source in enumerate(sources, start=1))
    fields.extend("|use" + str(index) + "=" + use for index, use in enumerate(uses, start=1))
    fields.append("}}")
    return "\n".join(fields)


def build_lifecycle_candidate(prefix: str) -> LifecycleCandidate:
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
        + "local tables = { Items = '__Items__', ObtainedFrom = '__ObtainedFrom__', UsedIn = '__UsedIn__' }\n"
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
        + _lifecycle_declare_items("__Items__")
        + "Temporary Cargo lifecycle storage probe."
        + "</noinclude>"
    )
    obtained_store = (
        "<includeonly>{{#invoke:"
        + module_name
        + "|storeObtainedFrom|itemkey={{{itemkey|}}}|source1={{{source1|}}}"
        + "|source2={{{source2|}}}|source3={{{source3|}}}}}</includeonly><noinclude>"
        + _lifecycle_declare_obtained_from("__ObtainedFrom__")
        + "Temporary.</noinclude>"
    )
    used_store = (
        "<includeonly>{{#invoke:"
        + module_name
        + "|storeUsedIn|itemkey={{{itemkey|}}}|use1={{{use1|}}}"
        + "|use2={{{use2|}}}|use3={{{use3|}}}}}</includeonly><noinclude>"
        + _lifecycle_declare_used_in("__UsedIn__")
        + "Temporary.</noinclude>"
    )
    initial_content = (
        _lifecycle_item_call(
            template_base,
            item_key,
            "Lifecycle Item A",
            ("SourceA1", "SourceA2", "SourceA3"),
            ("UseA1",),
        )
        + "\n"
        + _lifecycle_item_call(template_base, removed_key, "Lifecycle Item B", ("SourceB1",), ("UseB1",))
        + "\n"
    )
    reduced_content = (
        _lifecycle_item_call(template_base, item_key, "Lifecycle Item A", ("SourceA1",), ())
        + "\n"
        + _lifecycle_item_call(template_base, removed_key, "Lifecycle Item B", ("SourceB1",), ("UseB1",))
        + "\n"
    )
    removed_content = _lifecycle_item_call(template_base, item_key, "Lifecycle Item A", ("SourceA1",), ()) + "\n"

    return LifecycleCandidate(
        kind="lifecycle",
        page_title=page_title,
        template_base=template_base,
        tables=tables,
        templates=(
            TemplatePage(module_title, _fill_tables(module, tables)),
            TemplatePage(main_title, _fill_tables(main, tables)),
            TemplatePage(obtained_title, _fill_tables(obtained_store, tables)),
            TemplatePage(used_title, _fill_tables(used_store, tables)),
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


def api_post(client: MediaWikiClient, data: dict[str, Any], label: str) -> dict[str, Any]:
    try:
        return {"ok": True, "response": client._request({}, method="POST", data=data)}
    except MediaWikiAPIError as exc:
        return {"ok": False, "label": label, "code": exc.code, "info": exc.info, "error": str(exc)}


def assert_rights(client: MediaWikiClient) -> dict[str, Any]:
    payload = client._request(
        {
            "action": "query",
            "meta": "userinfo",
            "uiprop": "rights|groups",
            "formatversion": "2",
            "assert": "user",
            "assertuser": OWNER,
        }
    )
    userinfo = payload.get("query", {}).get("userinfo", {})
    rights = set(userinfo.get("rights", []))
    missing = sorted(REQUIRED_RIGHTS - rights)
    if missing:
        raise RuntimeError("Account is missing required rights: " + ", ".join(missing))
    return {
        "name": userinfo.get("name"),
        "groups": userinfo.get("groups", []),
        "required_rights_present": sorted(REQUIRED_RIGHTS),
    }


def page_exists(client: MediaWikiClient, title: str) -> bool:
    return client.get_page_revision_metadata(title, assertion="user", assert_user=OWNER) is not None


def create_page(client: MediaWikiClient, title: str, content: str) -> None:
    if page_exists(client, title):
        raise RuntimeError("Refusing to overwrite existing probe page: " + title)
    client.edit_page(title, content, summary="Create temporary Cargo storage probe", create_only=True, bot=True)


def recreate_tables(client: MediaWikiClient, template: str) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "response": client.recreate_cargo_tables(template, assertion="user", assert_user=OWNER),
        }
    except MediaWikiAPIError as exc:
        return {
            "ok": False,
            "label": "cargorecreatetables " + template,
            "code": exc.code,
            "info": exc.info,
            "error": str(exc),
        }


def recreate_data(client: MediaWikiClient, template: str, table: str) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "response": client.recreate_cargo_data(template, table, assertion="user", assert_user=OWNER),
        }
    except MediaWikiAPIError as exc:
        return {
            "ok": False,
            "label": "cargorecreatedata " + template + " " + table,
            "code": exc.code,
            "info": exc.info,
            "error": str(exc),
        }


def query_table(client: MediaWikiClient, table: str, key: str) -> dict[str, Any]:
    try:
        rows = client.query_cargo_table(
            tables=table,
            fields="_pageName=Page,ProbeKey,ProbeValue,ProbeFlag,ProbeNumber",
            where="ProbeKey='" + key + "'",
            limit=20,
            assertion="user",
            assert_user=OWNER,
        )
        return {"ok": True, "rows": rows}
    except MediaWikiAPIError as exc:
        return {"ok": False, "code": exc.code, "info": exc.info, "error": str(exc)}


def cargo_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def row_fields(row: dict[str, Any]) -> dict[str, Any]:
    title = row.get("title")
    if isinstance(title, dict):
        return title
    return row


def field_values(rows: list[dict[str, Any]], field: str) -> list[str]:
    return sorted(str(row_fields(row).get(field, "")) for row in rows)


def rows_empty(queries: dict[str, Any]) -> bool:
    return all(result.get("ok") and not result.get("rows", []) for result in queries.values())


def query_lifecycle_table(
    client: MediaWikiClient,
    table: str,
    fields: str,
    where: str,
) -> dict[str, Any]:
    try:
        rows = client.query_cargo_table(
            tables=table,
            fields=fields,
            where=where,
            limit=50,
            assertion="user",
            assert_user=OWNER,
        )
        return {"ok": True, "rows": rows}
    except MediaWikiAPIError as exc:
        return {"ok": False, "code": exc.code, "info": exc.info, "error": str(exc)}


def query_lifecycle_key(client: MediaWikiClient, candidate: LifecycleCandidate, key: str) -> dict[str, Any]:
    item_where = "StableKey=" + cargo_string_literal(key)
    relationship_where = "ItemKey=" + cargo_string_literal(key)
    return {
        "items": query_lifecycle_table(
            client,
            candidate.tables["Items"],
            "_pageName=Page,StableKey,DisplayName",
            item_where,
        ),
        "obtained_from": query_lifecycle_table(
            client,
            candidate.tables["ObtainedFrom"],
            "_pageName=Page,ItemKey,SourceKey,SourceIndex",
            relationship_where,
        ),
        "used_in": query_lifecycle_table(
            client,
            candidate.tables["UsedIn"],
            "_pageName=Page,ItemKey,UseKey,UseIndex",
            relationship_where,
        ),
    }


def query_lifecycle_state(client: MediaWikiClient, candidate: LifecycleCandidate) -> dict[str, Any]:
    return {
        candidate.item_key: query_lifecycle_key(client, candidate, candidate.item_key),
        candidate.removed_key: query_lifecycle_key(client, candidate, candidate.removed_key),
    }


def lifecycle_key_matches(
    state: dict[str, Any],
    key: str,
    source_keys: tuple[str, ...],
    use_keys: tuple[str, ...],
    item_present: bool = True,
) -> bool:
    key_state = state.get(key, {})
    if not all(result.get("ok") for result in key_state.values()):
        return False
    item_rows = key_state["items"].get("rows", [])
    obtained_rows = key_state["obtained_from"].get("rows", [])
    used_rows = key_state["used_in"].get("rows", [])
    if item_present:
        if field_values(item_rows, "StableKey") != [key]:
            return False
    elif item_rows:
        return False
    return field_values(obtained_rows, "SourceKey") == sorted(source_keys) and field_values(
        used_rows, "UseKey"
    ) == sorted(use_keys)


def lifecycle_state_matches(
    state: dict[str, Any],
    candidate: LifecycleCandidate,
    item_sources: tuple[str, ...],
    item_uses: tuple[str, ...],
    removed_sources: tuple[str, ...],
    removed_uses: tuple[str, ...],
    removed_present: bool,
    item_present: bool = True,
) -> bool:
    return lifecycle_key_matches(
        state,
        candidate.item_key,
        item_sources,
        item_uses,
        item_present=item_present,
    ) and lifecycle_key_matches(
        state,
        candidate.removed_key,
        removed_sources,
        removed_uses,
        item_present=removed_present,
    )


def wait_for_lifecycle_state(
    client: MediaWikiClient,
    candidate: LifecycleCandidate,
    seconds: int,
    item_sources: tuple[str, ...],
    item_uses: tuple[str, ...],
    removed_sources: tuple[str, ...],
    removed_uses: tuple[str, ...],
    removed_present: bool = True,
    item_present: bool = True,
) -> dict[str, Any]:
    deadline = time.time() + seconds
    attempts: list[dict[str, Any]] = []
    while True:
        state = query_lifecycle_state(client, candidate)
        matches = lifecycle_state_matches(
            state,
            candidate,
            item_sources,
            item_uses,
            removed_sources,
            removed_uses,
            removed_present=removed_present,
            item_present=item_present,
        )
        attempts.append({"elapsed_seconds": round(seconds - max(0, deadline - time.time()), 1), "state": state})
        if matches or time.time() >= deadline:
            return {"matches": matches, "final": state, "last_attempts": attempts[-5:]}
        time.sleep(5)


def edit_existing_page(client: MediaWikiClient, title: str, content: str, summary: str) -> None:
    client.edit_page(title, content, summary=summary, create_only=False, no_create=True, bot=True)


def query_all(client: MediaWikiClient, candidate: ProbeCandidate) -> dict[str, Any]:
    return {name: query_table(client, table, candidate.key) for name, table in candidate.tables.items()}


def rows_present(queries: dict[str, Any], expected_counts: dict[str, int]) -> bool:
    return all(
        result.get("ok") and len(result.get("rows", [])) == expected_counts[name] for name, result in queries.items()
    )


def wait_for_rows(client: MediaWikiClient, candidate: ProbeCandidate, seconds: int) -> dict[str, Any]:
    deadline = time.time() + seconds
    attempts: list[dict[str, Any]] = []
    while True:
        queries = query_all(client, candidate)
        attempts.append({"elapsed_seconds": round(seconds - max(0, deadline - time.time()), 1), "queries": queries})
        if rows_present(queries, candidate.expected_counts) or time.time() >= deadline:
            return {
                "present": rows_present(queries, candidate.expected_counts),
                "expected_counts": candidate.expected_counts,
                "final": queries,
                "last_attempts": attempts[-5:],
            }
        time.sleep(5)


def standard_candidate_validation(result: dict[str, Any], candidate: ProbeCandidate) -> bool:
    initial_queries = result.get("initial_queries", {})
    rendered_page = result.get("rendered_page", {})
    after_recreate = result.get("queries_after_cargorecreatetables", {})
    after_recreatedata = result.get("queries_after_cargorecreatedata", {})
    return (
        rows_present(initial_queries, candidate.expected_counts)
        and rendered_page.get("ok")
        and not rendered_page.get("contains_probe_text")
        and rows_empty(after_recreate)
        and rows_present(after_recreatedata, candidate.expected_counts)
    )


def parse_page_html(client: MediaWikiClient, page_title: str) -> dict[str, Any]:
    try:
        payload = client._request(
            {
                "action": "parse",
                "page": page_title,
                "prop": "text",
                "formatversion": "2",
                "assert": "user",
                "assertuser": OWNER,
            }
        )
        html = str(payload.get("parse", {}).get("text", ""))
        return {
            "ok": True,
            "html_length": len(html),
            "contains_probe_text": any(text in html for text in ("Temporary", "B1", "B2", "ProbeValue")),
        }
    except MediaWikiAPIError as exc:
        return {"ok": False, "code": exc.code, "info": exc.info, "error": str(exc)}


def delete_page(client: MediaWikiClient, title: str) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "response": client.delete_page(
                title,
                reason="Clean up temporary Cargo storage probe page",
                assertion="user",
                assert_user=OWNER,
            ),
        }
    except MediaWikiAPIError as exc:
        return {"ok": False, "label": "delete " + title, "code": exc.code, "info": exc.info, "error": str(exc)}


def run_candidate(client: MediaWikiClient, candidate: ProbeCandidate, poll_seconds: int) -> dict[str, Any]:
    created: list[str] = []
    result: dict[str, Any] = {
        "kind": candidate.kind,
        "key": candidate.key,
        "page_title": candidate.page_title,
        "tables": candidate.tables,
        "expected_counts": candidate.expected_counts,
        "manual_table_cleanup_urls": [MANUAL_DELETE_BASE + table for table in candidate.tables.values()],
    }
    try:
        for template in candidate.templates:
            create_page(client, template.title, template.content)
            created.append(template.title)
        result["initial_cargorecreatetables"] = [
            recreate_tables(client, template) for template in candidate.recreate_templates
        ]
        create_page(client, candidate.page_title, candidate.transclusion)
        created.append(candidate.page_title)
        result["purged"] = client.purge_pages(
            [candidate.page_title],
            force_link_update=True,
            assertion="user",
            assert_user=OWNER,
        )
        result["initial_queries"] = query_all(client, candidate)
        result["rendered_page"] = parse_page_html(client, candidate.page_title)
        result["post_page_cargorecreatetables"] = [
            recreate_tables(client, template) for template in candidate.recreate_templates
        ]
        result["queries_after_cargorecreatetables"] = query_all(client, candidate)
        result["wait_after_cargorecreatetables"] = wait_for_rows(client, candidate, poll_seconds)
        result["cargorecreatedata"] = [
            recreate_data(client, template, table) for template, table in candidate.recreatedata_pairs
        ]
        result["queries_after_cargorecreatedata"] = query_all(client, candidate)
        result["validation_ok"] = standard_candidate_validation(result, candidate)
    finally:
        cleanup: list[dict[str, Any]] = []
        for title in reversed(created):
            cleanup.append({"title": title, "result": delete_page(client, title)})
        result["page_cleanup"] = cleanup
    return result


def run_lifecycle_candidate(
    client: MediaWikiClient, candidate: LifecycleCandidate, poll_seconds: int
) -> dict[str, Any]:
    created: list[str] = []
    result: dict[str, Any] = {
        "kind": candidate.kind,
        "item_key": candidate.item_key,
        "removed_key": candidate.removed_key,
        "page_title": candidate.page_title,
        "tables": candidate.tables,
        "manual_table_cleanup_urls": [MANUAL_DELETE_BASE + table for table in candidate.tables.values()],
    }
    try:
        for template in candidate.templates:
            create_page(client, template.title, template.content)
            created.append(template.title)
        result["initial_cargorecreatetables"] = [
            recreate_tables(client, template) for template in candidate.recreate_templates
        ]
        create_page(client, candidate.page_title, candidate.initial_content)
        created.append(candidate.page_title)
        result["initial_purged"] = client.purge_pages(
            [candidate.page_title],
            force_link_update=True,
            assertion="user",
            assert_user=OWNER,
        )
        result["initial_state"] = wait_for_lifecycle_state(
            client,
            candidate,
            poll_seconds,
            item_sources=("SourceA1", "SourceA2", "SourceA3"),
            item_uses=("UseA1",),
            removed_sources=("SourceB1",),
            removed_uses=("UseB1",),
        )
        edit_existing_page(
            client,
            candidate.page_title,
            candidate.reduced_content,
            "Reduce temporary Cargo lifecycle probe rows",
        )
        result["reduced_purged"] = client.purge_pages(
            [candidate.page_title],
            force_link_update=True,
            assertion="user",
            assert_user=OWNER,
        )
        result["reduced_state"] = wait_for_lifecycle_state(
            client,
            candidate,
            poll_seconds,
            item_sources=("SourceA1",),
            item_uses=(),
            removed_sources=("SourceB1",),
            removed_uses=("UseB1",),
        )
        edit_existing_page(
            client,
            candidate.page_title,
            candidate.removed_content,
            "Remove one temporary Cargo lifecycle probe item",
        )
        result["removed_purged"] = client.purge_pages(
            [candidate.page_title],
            force_link_update=True,
            assertion="user",
            assert_user=OWNER,
        )
        result["removed_item_state"] = wait_for_lifecycle_state(
            client,
            candidate,
            poll_seconds,
            item_sources=("SourceA1",),
            item_uses=(),
            removed_sources=(),
            removed_uses=(),
            removed_present=False,
        )
        result["delete_page"] = delete_page(client, candidate.page_title)
        if result["delete_page"].get("ok"):
            created.remove(candidate.page_title)
        result["after_delete_state"] = query_lifecycle_state(client, candidate)
        result["after_delete_rows_removed"] = lifecycle_state_matches(
            result["after_delete_state"],
            candidate,
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
        cleanup: list[dict[str, Any]] = []
        for title in reversed(created):
            cleanup.append({"title": title, "result": delete_page(client, title)})
        result["page_cleanup"] = cleanup
    return result


def run_probe_candidate(client: MediaWikiClient, candidate: Candidate, poll_seconds: int) -> dict[str, Any]:
    if isinstance(candidate, LifecycleCandidate):
        return run_lifecycle_candidate(client, candidate, poll_seconds)
    return run_candidate(client, candidate, poll_seconds)


def build_candidates(prefix: str, choice: str) -> list[Candidate]:
    if choice == "direct":
        return [build_direct_candidate(prefix)]
    if choice == "nested":
        return [build_nested_candidate(prefix)]
    if choice == "lua-nested":
        return [build_lua_nested_candidate(prefix)]
    if choice == "lifecycle":
        return [build_lifecycle_candidate(prefix)]
    if choice == "both":
        return [build_direct_candidate(prefix), build_nested_candidate(prefix)]
    return [
        build_direct_candidate(prefix),
        build_nested_candidate(prefix),
        build_lua_nested_candidate(prefix),
        build_lifecycle_candidate(prefix),
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="perform live writes; omitted means dry-run only")
    parser.add_argument(
        "--candidate",
        choices=("direct", "nested", "lua-nested", "lifecycle", "both", "all"),
        default="lua-nested",
    )
    parser.add_argument(
        "--prefix",
        default="CargoStorageProbe" + datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=75,
        help="seconds to poll for automatic rows after cargorecreatetables",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    candidates = build_candidates(args.prefix, args.candidate)
    dry_run_summary = {
        "live": args.live,
        "prefix": args.prefix,
        "candidate": args.candidate,
        "pages": [candidate.page_title for candidate in candidates]
        + [template.title for candidate in candidates for template in candidate.templates],
        "tables": [table for candidate in candidates for table in candidate.tables.values()],
        "manual_table_cleanup_urls": [
            MANUAL_DELETE_BASE + table for candidate in candidates for table in candidate.tables.values()
        ],
    }
    if not args.live:
        print(json.dumps({"dry_run": dry_run_summary}, indent=2, sort_keys=True))
        return 0

    cfg = load_config().global_.mediawiki
    result: dict[str, Any] = {"dry_run": dry_run_summary, "candidates": []}
    client = MediaWikiClient(
        api_url=cfg.api_url,
        bot_username=cfg.bot_username,
        bot_password=cfg.bot_password,
        rate_limit_delay=1.0,
        timeout=60.0,
        edit_summary="Run temporary Cargo storage probe",
    )
    try:
        client.login()
        result["account"] = assert_rights(client)
        for candidate in candidates:
            result["candidates"].append(run_probe_candidate(client, candidate, args.poll_seconds))
    finally:
        client.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    failed_cleanup = [
        cleanup
        for candidate in result.get("candidates", [])
        for cleanup in candidate.get("page_cleanup", [])
        if not cleanup.get("result", {}).get("ok")
    ]
    failed_validation = [
        candidate for candidate in result.get("candidates", []) if candidate.get("validation_ok") is False
    ]
    if failed_cleanup:
        return 2
    if failed_validation:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
