from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from typing import Any

from erenshor.infrastructure.config.loader import load_config
from erenshor.infrastructure.wiki.client import MediaWikiClient

from .models import OWNER, REQUIRED_RIGHTS, manual_cleanup_urls
from .operations import ProbeRunContext
from .registry import build_scenarios, candidate_choices


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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="perform live writes; omitted means dry-run only")
    parser.add_argument(
        "--candidate",
        choices=candidate_choices(),
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
    parser.add_argument(
        "--batch-pages",
        type=int,
        default=25,
        help="number of sandbox item pages for the recreate-batching candidate",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    scenarios = build_scenarios(args.prefix, args.candidate, args.batch_pages)
    table_names = [table for scenario in scenarios for table in scenario.table_names]
    dry_run_summary = {
        "live": args.live,
        "prefix": args.prefix,
        "candidate": args.candidate,
        "batch_pages": args.batch_pages,
        "pages": [title for scenario in scenarios for title in scenario.page_titles]
        + [template.title for scenario in scenarios for template in scenario.template_pages],
        "tables": table_names,
        "manual_table_cleanup_urls": manual_cleanup_urls(table_names),
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
        for scenario in scenarios:
            context = ProbeRunContext(client)
            result["candidates"].append(scenario.run(context, args.poll_seconds))
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
