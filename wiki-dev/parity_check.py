#!/usr/bin/env python3
"""Live-vs-local MediaWiki rendering parity gate.

Default mode renders the local fixture pages and checks them against the
committed contract's baseline, failing loudly on any divergence. ``--capture``
renders the live wiki and refreshes the gitignored baseline; nothing captured
from live is committed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from parity.runner import (
    DEFAULT_BASELINE,
    DEFAULT_LIVE_BASE,
    DEFAULT_LOCAL_BASE,
    capture,
    check,
    print_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Capture the baseline from the live wiki instead of checking local.",
    )
    parser.add_argument("--base-url", default=DEFAULT_LOCAL_BASE, help="Local wiki base URL")
    parser.add_argument("--live-base", default=DEFAULT_LIVE_BASE, help="Live wiki base URL for capture")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Captured baseline path (gitignored)",
    )
    args = parser.parse_args()

    if args.capture:
        snapshot = capture(live_base=args.live_base, baseline_path=args.baseline)
        targets = sum(len(component) for component in snapshot.values())
        print(f"Captured {len(snapshot)} pages, {targets} targets to {args.baseline}")
        return

    divergences = check(local_base=args.base_url, baseline_path=args.baseline)
    print_report(divergences)
    if divergences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
