#!/usr/bin/env python3
"""Update stale live wiki vendor inventory tables without touching article prose.

The tool reads current inventories from the clean main database, fetches the live
vendor pages, and replaces only the ``Store inventory`` wikitable. Missing tables
are inserted before trailing category tags. It defaults to a diff-only dry run;
``--live`` uses native guarded edits and retains their durable rollback manifest.

Usage:
    uv run python src/tools/update_vendor_inventory_tables.py
    uv run python src/tools/update_vendor_inventory_tables.py --page "Pierson Windwash"
    uv run python src/tools/update_vendor_inventory_tables.py --live
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Literal, cast

from erenshor.application.wiki_deploy.guarded_edits import GuardedEditResult, GuardedPageEdit, apply_guarded_edits
from erenshor.application.wiki_deploy.manifest import read_repo_page_manifest
from erenshor.infrastructure.config.loader import get_repo_root, load_config
from erenshor.infrastructure.config.paths import require_owned_write_path
from erenshor.infrastructure.wiki.client import MediaWikiClient, MediaWikiPageSnapshot
from erenshor.tools.vendor_inventory_tables import (
    DEFAULT_DATABASE,
    ExistingInventoryItem,
    VendorInventory,
    existing_type_index,
    load_vendor_inventories,
    parse_inventory_table,
    render_inventory_table,
    replace_inventory_table,
)

EDIT_SUMMARY = "Update vendor inventory from current game data"


@dataclass(frozen=True)
class Arguments:
    database: Path
    pages: tuple[str, ...]
    limit: int | None
    live: bool
    summary_only: bool


@dataclass(frozen=True)
class PendingUpdate:
    inventory: VendorInventory
    snapshot: MediaWikiPageSnapshot
    updated_text: str


def parse_args(argv: list[str]) -> Arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    _ = parser.add_argument(
        "--page",
        action="append",
        default=[],
        help="update only this vendor page; repeat for multiple pages",
    )
    _ = parser.add_argument("--limit", type=int, help="limit the sorted set of selected vendor pages")
    _ = parser.add_argument("--live", action="store_true", help="perform conflict-guarded live edits")
    _ = parser.add_argument("--summary-only", action="store_true", help="suppress dry-run unified diffs")
    namespace = parser.parse_args(argv)
    limit = cast("int | None", namespace.limit)
    if limit is not None and limit <= 0:
        parser.error("--limit must be greater than zero")
    return Arguments(
        database=cast("Path", namespace.database),
        pages=tuple(cast("list[str]", namespace.page)),
        limit=limit,
        live=cast("bool", namespace.live),
        summary_only=cast("bool", namespace.summary_only),
    )


def select_inventories(
    inventories: tuple[VendorInventory, ...],
    pages: tuple[str, ...],
    limit: int | None,
) -> tuple[VendorInventory, ...]:
    by_page = {inventory.page: inventory for inventory in inventories}
    if pages:
        unknown = sorted(set(pages) - by_page.keys())
        if unknown:
            raise ValueError("Unknown vendor page(s): " + ", ".join(unknown))
        selected = tuple(by_page[page] for page in dict.fromkeys(pages))
    else:
        selected = inventories
    return selected[:limit] if limit is not None else selected


def build_updates(
    inventories: tuple[VendorInventory, ...],
    snapshots: dict[str, MediaWikiPageSnapshot],
) -> tuple[PendingUpdate, ...]:
    existing_tables: dict[str, tuple[ExistingInventoryItem, ...] | None] = {}
    for inventory in inventories:
        snapshot = snapshots[inventory.page]
        if snapshot.source_text is None or snapshot.revision is None:
            raise ValueError(f"Live vendor page is missing or has no revision: {inventory.page}")
        existing_tables[inventory.page] = parse_inventory_table(snapshot.source_text)

    known_types = existing_type_index(existing_tables)
    updates: list[PendingUpdate] = []
    for inventory in inventories:
        snapshot = snapshots[inventory.page]
        assert snapshot.source_text is not None
        table = render_inventory_table(inventory, known_types)
        updated_text = replace_inventory_table(snapshot.source_text, table)
        if updated_text == snapshot.source_text:
            continue
        updates.append(PendingUpdate(inventory=inventory, snapshot=snapshot, updated_text=updated_text))
    return tuple(updates)


def print_plan(updates: tuple[PendingUpdate, ...], selected_count: int, *, show_diff: bool) -> None:
    mode = "Would update" if show_diff else "Selected"
    print(f"{mode} {len(updates)} of {selected_count} vendor pages:")
    for update in updates:
        print(f"- {update.inventory.page}")
        if show_diff:
            assert update.snapshot.source_text is not None
            diff = unified_diff(
                update.snapshot.source_text.splitlines(keepends=True),
                update.updated_text.splitlines(keepends=True),
                fromfile=f"live/{update.inventory.page}",
                tofile=f"updated/{update.inventory.page}",
            )
            _ = sys.stdout.writelines(diff)


def update_live(
    client: MediaWikiClient,
    updates: tuple[PendingUpdate, ...],
    *,
    repo_root: Path,
    run_dir: Path,
    wiki_root: Path,
) -> GuardedEditResult:
    edits = []
    for update in updates:
        snapshot = update.snapshot
        if snapshot.revision is None or snapshot.source_text is None:
            raise ValueError(f"Cannot safely edit page without a complete base: {update.inventory.page}")
        if snapshot.content_model != "wikitext":
            raise ValueError(f"Vendor inventory page must use wikitext: {update.inventory.page}")
        edits.append(
            GuardedPageEdit(
                update.inventory.page,
                EDIT_SUMMARY,
                update.updated_text,
                snapshot.source_text,
                snapshot.revision,
                content_model="wikitext",
            )
        )
    require_owned_write_path(run_dir, repo_root)
    result = apply_guarded_edits(
        edits,
        repo_root=repo_root,
        run_dir=run_dir,
        client=client,
        assert_user=client.edit_account,
        variant="main",
        wiki_root=wiki_root,
        stop_on_conflict=True,
    )
    print(f"Native manifest: {result.manifest_path}")
    manifest = read_repo_page_manifest(result.manifest_path)
    for entry in manifest.entries:
        if entry.new_revision_id is not None:
            state = "Write requires recovery" if entry.requires_rollback else "Updated"
            print(f"{state} {entry.title}: revision {entry.new_revision_id}")
    if result.failed:
        raise RuntimeError(
            f"Vendor publication stopped: {result.stopped or result.conflicts}. "
            f"Retain native recovery manifest {result.manifest_path}"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    inventories = select_inventories(load_vendor_inventories(args.database), args.pages, args.limit)
    project = load_config()
    config = project.global_.mediawiki
    client = MediaWikiClient(
        api_url=config.api_url,
        bot_username=config.bot_username,
        bot_password=config.bot_password,
        timeout=60.0,
        edit_summary=EDIT_SUMMARY,
    )
    try:
        if args.live:
            client.login()
        assertion: Literal["bot"] | None = "bot" if args.live else None
        snapshots = client.get_page_snapshots(
            [inventory.page for inventory in inventories],
            assertion=assertion,
        )
        updates = build_updates(inventories, snapshots)
        print_plan(updates, len(inventories), show_diff=not args.live and not args.summary_only)
        if args.live:
            repo_root = get_repo_root()
            wiki_root = project.variants["main"].resolved_wiki(repo_root)
            runs = wiki_root / "vendor-page-edits"
            require_owned_write_path(runs, repo_root)
            runs.mkdir(parents=True, exist_ok=True)
            run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=runs))
            update_live(client, updates, repo_root=repo_root, run_dir=run_dir, wiki_root=wiki_root)
        else:
            print("Dry run only; pass --live to apply these conflict-guarded edits.")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
