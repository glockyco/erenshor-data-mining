from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from loguru import logger

STATE_DIR = Path(".erenshor")
STATE_FILE = STATE_DIR / "capture-state.json"


class CaptureState:
    """Tracks per-zone, per-variant capture completion and checksums."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    # -- persistence ----------------------------------------------------------

    @classmethod
    def load(cls, repo_root: Path) -> CaptureState:
        """Load state from disk, creating a default if the file is missing."""
        path = repo_root / STATE_FILE
        if path.exists():
            data = json.loads(path.read_text())
            logger.debug(f"Loaded capture state from {path}")
        else:
            data = {"zones": {}}
            logger.info("No capture state found; starting fresh")
        return cls(data)

    def save(self, repo_root: Path) -> None:
        """Persist current state to disk."""
        path = repo_root / STATE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._data, indent=2) + "\n")
        logger.debug(f"Saved capture state to {path}")

    # -- accessors ------------------------------------------------------------

    def get_variant_state(self, zone: str, variant: str) -> dict[str, Any] | None:
        """Return the state dict for a zone/variant, or None."""
        return self._data.get("zones", {}).get(zone, {}).get(variant)

    def set_variant_state(self, zone: str, variant: str, data: dict[str, Any]) -> None:
        """Upsert state for a zone/variant."""
        zones = self._data.setdefault("zones", {})
        zones.setdefault(zone, {})[variant] = data

    def should_skip(
        self, zone: str, variant: str, master_path: Path, *, force: bool = False
    ) -> bool:
        """Return True when the zone/variant is already captured and unchanged.

        Skips when all of:
        - force is False
        - variant state exists with status == "ok"
        - master PNG exists and its sha256 matches the stored checksum
        """
        if force:
            return False
        vs = self.get_variant_state(zone, variant)
        if vs is None or vs.get("status") != "ok":
            return False
        stored = vs.get("masterChecksum")
        if not stored or not master_path.exists():
            return False
        return _sha256(master_path) == stored


def _sha256(path: Path) -> str:
    """Compute hex sha256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
