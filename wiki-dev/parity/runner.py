"""Capture/check orchestration for the live-vs-local parity gate.

``capture`` renders the live wiki and writes the gitignored baseline.
``check`` renders the local fixture pages and compares them against that
baseline. ``print_report`` emits PASS/FAIL lines per contract page, matching
the smoke harness output style.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .compare import compare_snapshots, load_baseline, save_baseline
from .contract import PAGES
from .extract import extract_snapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .compare import Divergence, Snapshot
    from .contract import Target

DEFAULT_LIVE_BASE = "https://erenshor.wiki.gg"
DEFAULT_LOCAL_BASE = "http://localhost:8088"
DEFAULT_BASELINE = Path("wiki-dev/parity/baseline.json")


def _live_pages(base: str) -> list[tuple[str, str, Sequence[Target]]]:
    root = base.rstrip("/")
    return [(page.name, f"{root}{page.live_path}", page.targets) for page in PAGES]


def _local_pages(base: str) -> list[tuple[str, str, Sequence[Target]]]:
    root = base.rstrip("/")
    return [(page.name, f"{root}/index.php?title={page.local_title}", page.targets) for page in PAGES]


def capture(*, live_base: str, baseline_path: Path, headless: bool = False) -> Snapshot:
    """Render the live wiki and write the captured baseline.

    Capture defaults to a headed browser: the live wiki sits behind a Cloudflare
    JS challenge that a headless Chromium does not clear. Capture is an occasional
    dev action, while ``check`` runs headless against the local stack.
    """
    snapshot = extract_snapshot(_live_pages(live_base), headless=headless)
    save_baseline(baseline_path, snapshot)
    return snapshot


def check(*, local_base: str, baseline_path: Path, headless: bool = True) -> list[Divergence]:
    """Render local fixture pages and compare them against the baseline."""
    baseline = load_baseline(baseline_path)
    actual = extract_snapshot(_local_pages(local_base), headless=headless)
    return compare_snapshots(baseline, actual)


def print_report(divergences: list[Divergence]) -> None:
    """Print PASS/FAIL lines per contract page with divergence detail."""
    failed = {divergence.component for divergence in divergences}
    for page in PAGES:
        if page.name not in failed:
            print(f"PASS {page.name}")
            continue
        print(f"FAIL {page.name}")
        for divergence in divergences:
            if divergence.component == page.name:
                print(f"  - {divergence.describe()}")
