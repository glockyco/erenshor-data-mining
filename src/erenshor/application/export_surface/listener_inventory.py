"""Static contracts for the Unity export listener inventory.

This module intentionally does not import Unity or execute registration actions.
It reads the source declaration only, so inventory/dependency checks remain
independent from the shipped-game field coverage and listener declaration gates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ListenerInventoryEntry:
    key: str
    label: str
    channel: str
    dependencies: tuple[str, ...]


_ENTRY_RE = re.compile(
    r"""new\(\s*"(?P<key>[^"]+)"\s*,\s*"(?P<label>[^"]+)"\s*,\s*"""
    r"""ExportScanChannel\.(?P<channel>[A-Za-z]+)\s*,\s*"""
    r"""(?P<dependencies>Array\.Empty<string>\(\)|new\[\]\s*\{(?P<dependency_text>[^}]*)\})"""
)
_DEPENDENCY_RE = re.compile(r'"([^"]+)"')


def read_listener_inventory(path: Path) -> tuple[ListenerInventoryEntry, ...]:
    """Read ordered listener declarations from ``ExportListenerRegistry.cs``."""
    source = path.read_text(encoding="utf-8")
    entries = tuple(
        ListenerInventoryEntry(
            key=match.group("key"),
            label=match.group("label"),
            channel=match.group("channel"),
            dependencies=tuple(_DEPENDENCY_RE.findall(match.group("dependency_text") or "")),
        )
        for match in _ENTRY_RE.finditer(source)
    )
    if not entries:
        raise ValueError(f"No listener declarations found in {path}")
    declarations = source.count('new("')
    if declarations != len(entries):
        raise ValueError(
            f"Could not parse all listener declarations in {path}: parsed {len(entries)} of {declarations}"
        )
    return entries


def validate_listener_inventory(
    entries: tuple[ListenerInventoryEntry, ...],
    selected_keys: set[str] | None = None,
) -> None:
    """Validate key uniqueness, dependency references, and ordered dependencies."""
    known = {entry.key for entry in entries}
    if len(known) != len(entries):
        raise ValueError("listener keys must be unique")
    positions = {entry.key: index for index, entry in enumerate(entries)}
    for entry in entries:
        for dependency in entry.dependencies:
            if dependency not in known:
                raise ValueError(f"listener {entry.key!r} depends on unknown key {dependency!r}")
            if positions[dependency] >= positions[entry.key]:
                raise ValueError(f"listener {entry.key!r} depends on later key {dependency!r}")
    if selected_keys is not None:
        unknown = selected_keys - known
        if unknown:
            raise ValueError(f"unknown listener keys: {sorted(unknown)!r}")
        for entry in entries:
            if entry.key in selected_keys:
                missing = set(entry.dependencies) - selected_keys
                if missing:
                    raise ValueError(f"listener {entry.key!r} requires selected dependencies: {sorted(missing)!r}")
