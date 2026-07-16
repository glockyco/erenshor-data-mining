#!/usr/bin/env python3
"""Update stale live wiki vendor inventory tables without touching article prose.

The tool reads current inventories from the clean main database, fetches the live
vendor pages, and replaces only the ``Store inventory`` wikitable. Missing tables
are inserted before trailing category tags. It defaults to a diff-only dry run;
``--live`` enables conflict-guarded MediaWiki edits.

Usage:
    uv run python src/tools/update_vendor_inventory_tables.py
    uv run python src/tools/update_vendor_inventory_tables.py --page "Pierson Windwash"
    uv run python src/tools/update_vendor_inventory_tables.py --live
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Literal, cast

from erenshor.infrastructure.config.loader import load_config
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


def update_live(client: MediaWikiClient, updates: tuple[PendingUpdate, ...]) -> None:
    for update in updates:
        revision = update.snapshot.revision
        if revision is None:
            raise ValueError(f"Cannot safely edit page without a base revision: {update.inventory.page}")
        new_revision = client.safe_edit_page(
            title=update.inventory.page,
            content=update.updated_text,
            base_revision=revision,
            summary=EDIT_SUMMARY,
            assertion="bot",
            content_model="wikitext",
        )
        print(f"Updated {update.inventory.page}: revision {revision.revision_id} -> {new_revision}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    inventories = select_inventories(load_vendor_inventories(args.database), args.pages, args.limit)
    config = load_config().global_.mediawiki
    client = MediaWikiClient(
        api_url=config.api_url,
        bot_username=config.bot_username,
        bot_password=config.bot_password,
        rate_limit_delay=1.0,
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
            update_live(client, updates)
        else:
            print("Dry run only; pass --live to apply these conflict-guarded edits.")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
