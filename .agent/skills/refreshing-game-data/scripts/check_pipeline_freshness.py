#!/usr/bin/env python3
"""Preflight freshness check before refreshing a variant's data pipeline.

Reports mtimes for the variant's game files, Unity ExportedProject, raw and
clean SQLite databases. Exits 1 if a re-rip is needed (ExportedProject older
than game files, or missing entirely). Exits 0 otherwise.

Also prints level-file and sharedassets bundle counts so a content delta
(new zones, new asset bundles) is visible at a glance.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", help="variant name (e.g. main, playtest, demo)")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="repo root (default: cwd)",
    )
    args = parser.parse_args()

    v = args.variant
    root = args.repo_root / "variants" / v
    targets = {
        "game files": root / "game" / "Erenshor_Data",
        "Unity ExportedProject": root / "unity" / "ExportedProject",
        "raw SQLite": root / f"erenshor-{v}-raw.sqlite",
        "clean SQLite": root / f"erenshor-{v}.sqlite",
    }

    print(f"Variant: {v}")
    times: dict[str, float | None] = {}
    for name, path in targets.items():
        if path.exists():
            mt = path.stat().st_mtime
            times[name] = mt
            stamp = datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")
            print(f"  {name:<24s} {stamp:<18s} {path}")
        else:
            times[name] = None
            print(f"  {name:<24s} {'MISSING':<18s} {path}")

    game_mt = times["game files"]
    unity_mt = times["Unity ExportedProject"]

    if game_mt is None:
        print(
            f"\nNo game files present. Run `erenshor -V {v} extract download` first.",
            file=sys.stderr,
        )
        return 1

    # Asset counts (signal of content delta vs. metadata-only Steam patch)
    erenshor_data = root / "game" / "Erenshor_Data"
    levels = list(erenshor_data.glob("level*"))
    sharedassets = list(erenshor_data.glob("sharedassets*.assets"))
    print(f"  asset counts: {len(levels)} levels, {len(sharedassets)} sharedassets bundles")

    if unity_mt is None:
        print("\nRe-rip needed: ExportedProject is missing.")
        return 1

    if unity_mt < game_mt:
        delta_hours = (game_mt - unity_mt) / 3600
        print(f"\nRe-rip needed: ExportedProject is {delta_hours:.1f}h older than game files.")
        return 1

    raw_mt = times["raw SQLite"]
    clean_mt = times["clean SQLite"]
    if raw_mt is None and clean_mt is not None:
        print("\nWARNING: clean SQLite exists but raw SQLite is missing; treat clean as untrusted.")
        return 1

    print("\nUnity project is fresh (no re-rip needed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
