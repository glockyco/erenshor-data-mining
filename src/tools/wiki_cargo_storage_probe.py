#!/usr/bin/env python3
"""Probe live wiki.gg Cargo storage and recreate behavior.

This tool intentionally defaults to a dry run. Pass ``--live`` to create temporary
sandbox templates/pages on the configured MediaWiki target. Live runs delete the
sandbox pages they create, but Cargo tables require manual admin cleanup through
Special:CargoTables / Special:DeleteCargoTable.

Usage:
    uv run python src/tools/wiki_cargo_storage_probe.py
    uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate nested
    uv run python src/tools/wiki_cargo_storage_probe.py --live --candidate both --prefix Probe20260709
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

CandidateKind = Literal["direct", "nested"]


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
    templates: tuple[TemplatePage, ...]
    recreate_templates: tuple[str, ...]
    recreatedata_pairs: tuple[tuple[str, str], ...]

    @property
    def transclusion(self) -> str:
        return "{{" + self.template_base + "Main|key=" + self.key + "}}\n"

    @property
    def cleanup_titles(self) -> tuple[str, ...]:
        return (self.page_title, *[template.title for template in reversed(self.templates)])


def _store(table_placeholder: str, value: str) -> str:
    return "{{#cargo_store:_table=" + table_placeholder + "|ProbeKey={{{key|}}}|ProbeValue=" + value + "}}"


def _declare(table_placeholder: str) -> str:
    return "{{#cargo_declare:_table=" + table_placeholder + "|ProbeKey=String|ProbeValue=String}}"


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
        + _store("__A__", "A")
        + _store("__B__", "B")
        + _store("__C__", "C")
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
        + _store("__A__", "A")
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
        + _store("__B__", "B")
        + "</includeonly><noinclude>"
        + _declare("__B__")
        + "Temporary.</noinclude>"
    )
    c_store = (
        "<includeonly>"
        + _store("__C__", "C")
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


def _fill_tables(content: str, tables: dict[str, str]) -> str:
    for name, table in tables.items():
        content = content.replace("__" + name + "__", table)
    return content


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
    return api_post(
        client,
        {
            "action": "cargorecreatetables",
            "template": template,
            "token": client.get_csrf_token(),
            "formatversion": "2",
            "assert": "user",
            "assertuser": OWNER,
        },
        "cargorecreatetables " + template,
    )


def recreate_data(client: MediaWikiClient, template: str, table: str) -> dict[str, Any]:
    return api_post(
        client,
        {
            "action": "cargorecreatedata",
            "template": template,
            "table": table,
            "offset": "0",
            "replaceOldRows": "1",
            "token": client.get_csrf_token(),
            "formatversion": "2",
            "assert": "user",
            "assertuser": OWNER,
        },
        "cargorecreatedata " + template + " " + table,
    )


def query_table(client: MediaWikiClient, table: str, key: str) -> dict[str, Any]:
    try:
        payload = client._request(
            {
                "action": "cargoquery",
                "tables": table,
                "fields": "_pageName=Page,ProbeKey,ProbeValue",
                "where": "ProbeKey='" + key + "'",
                "limit": "20",
                "formatversion": "2",
                "assert": "user",
                "assertuser": OWNER,
            }
        )
        return {"ok": True, "rows": payload.get("cargoquery", [])}
    except MediaWikiAPIError as exc:
        return {"ok": False, "code": exc.code, "info": exc.info, "error": str(exc)}


def query_all(client: MediaWikiClient, candidate: ProbeCandidate) -> dict[str, Any]:
    return {name: query_table(client, table, candidate.key) for name, table in candidate.tables.items()}


def rows_present(queries: dict[str, Any]) -> bool:
    return all(result.get("ok") and len(result.get("rows", [])) > 0 for result in queries.values())


def wait_for_rows(client: MediaWikiClient, candidate: ProbeCandidate, seconds: int) -> dict[str, Any]:
    deadline = time.time() + seconds
    attempts: list[dict[str, Any]] = []
    while True:
        queries = query_all(client, candidate)
        attempts.append({"elapsed_seconds": round(seconds - max(0, deadline - time.time()), 1), "queries": queries})
        if rows_present(queries) or time.time() >= deadline:
            return {"present": rows_present(queries), "final": queries, "last_attempts": attempts[-5:]}
        time.sleep(5)


def delete_page(client: MediaWikiClient, title: str) -> dict[str, Any]:
    return api_post(
        client,
        {
            "action": "delete",
            "title": title,
            "token": client.get_csrf_token(),
            "reason": "Clean up temporary Cargo storage probe page",
            "formatversion": "2",
            "assert": "user",
            "assertuser": OWNER,
        },
        "delete " + title,
    )


def run_candidate(client: MediaWikiClient, candidate: ProbeCandidate, poll_seconds: int) -> dict[str, Any]:
    created: list[str] = []
    result: dict[str, Any] = {
        "kind": candidate.kind,
        "key": candidate.key,
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
        create_page(client, candidate.page_title, candidate.transclusion)
        created.append(candidate.page_title)
        result["purged"] = client.purge_pages(
            [candidate.page_title],
            force_link_update=True,
            assertion="user",
            assert_user=OWNER,
        )
        result["initial_queries"] = query_all(client, candidate)
        result["post_page_cargorecreatetables"] = [
            recreate_tables(client, template) for template in candidate.recreate_templates
        ]
        result["queries_after_cargorecreatetables"] = query_all(client, candidate)
        result["wait_after_cargorecreatetables"] = wait_for_rows(client, candidate, poll_seconds)
        result["cargorecreatedata"] = [
            recreate_data(client, template, table) for template, table in candidate.recreatedata_pairs
        ]
        result["queries_after_cargorecreatedata"] = query_all(client, candidate)
    finally:
        cleanup: list[dict[str, Any]] = []
        for title in reversed(created):
            cleanup.append({"title": title, "result": delete_page(client, title)})
        result["page_cleanup"] = cleanup
    return result


def build_candidates(prefix: str, choice: str) -> list[ProbeCandidate]:
    if choice == "direct":
        return [build_direct_candidate(prefix)]
    if choice == "nested":
        return [build_nested_candidate(prefix)]
    return [build_direct_candidate(prefix), build_nested_candidate(prefix)]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="perform live writes; omitted means dry-run only")
    parser.add_argument("--candidate", choices=("direct", "nested", "both"), default="nested")
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
            result["candidates"].append(run_candidate(client, candidate, args.poll_seconds))
    finally:
        client.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    failed_cleanup = [
        cleanup
        for candidate in result.get("candidates", [])
        for cleanup in candidate.get("page_cleanup", [])
        if not cleanup.get("result", {}).get("ok")
    ]
    if failed_cleanup:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
