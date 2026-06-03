"""Pure comparison logic for live-vs-local wiki rendering parity.

This module is intentionally dependency-free (no Playwright, no HTTP) so the
comparison contract can be unit-tested in isolation. A *snapshot* maps a
component name to its targets, and each target to a flat map of property keys
and their string values:

    {component: {target: {property: value}}}

The committed contract (``contract.py``) defines which components, targets, and
properties exist. The expected values come from a baseline captured from the
live wiki; the actual values come from rendering local pages. ``baseline.json``
is gitignored because it is derived from third-party live content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

Snapshot = dict[str, dict[str, dict[str, str]]]


@dataclass(frozen=True)
class Divergence:
    """One parity mismatch between a baseline and an actual snapshot."""

    component: str
    target: str
    prop: str
    expected: str | None
    actual: str | None
    kind: str

    def describe(self) -> str:
        """Return a single human-readable line for reporting."""
        location = f"{self.component} > {self.target}"
        if self.kind == "missing-target":
            return f"{location}: target not rendered locally"
        if self.kind == "missing-property":
            return f"{location} > {self.prop}: missing locally (expected {self.expected!r})"
        return f"{location} > {self.prop}: expected {self.expected!r}, got {self.actual!r}"


def compare_snapshots(baseline: Snapshot, actual: Snapshot) -> list[Divergence]:
    """Return divergences where ``actual`` does not satisfy ``baseline``.

    The baseline is the contract: every component/target/property it contains
    must be present and equal in ``actual``. Targets and properties that only
    appear in ``actual`` are ignored, so unrelated additions never fail parity.
    Comparison is whitespace-insensitive string equality.
    """
    divergences: list[Divergence] = []
    for component in sorted(baseline):
        actual_component = actual.get(component, {})
        for target in sorted(baseline[component]):
            if target not in actual_component:
                divergences.append(
                    Divergence(
                        component=component,
                        target=target,
                        prop="",
                        expected=None,
                        actual=None,
                        kind="missing-target",
                    )
                )
                continue
            actual_props = actual_component[target]
            for prop in sorted(baseline[component][target]):
                expected = baseline[component][target][prop]
                if prop not in actual_props:
                    divergences.append(
                        Divergence(
                            component=component,
                            target=target,
                            prop=prop,
                            expected=expected,
                            actual=None,
                            kind="missing-property",
                        )
                    )
                    continue
                actual_value = actual_props[prop]
                if expected.strip() != actual_value.strip():
                    divergences.append(
                        Divergence(
                            component=component,
                            target=target,
                            prop=prop,
                            expected=expected,
                            actual=actual_value,
                            kind="value",
                        )
                    )
    return divergences


def save_baseline(path: Path, snapshot: Snapshot) -> None:
    """Write a captured baseline snapshot as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> Snapshot:
    """Load a captured baseline snapshot, failing loudly when it is absent."""
    if not path.exists():
        raise FileNotFoundError(
            f"Parity baseline is missing: {path}. Run `uv run python wiki-dev/parity_check.py --capture` "
            "to capture it from the live wiki first."
        )
    data: Snapshot = json.loads(path.read_text(encoding="utf-8"))
    return data
