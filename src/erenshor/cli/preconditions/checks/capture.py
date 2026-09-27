"""Capture inputs checked before a pipeline writes any tiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from erenshor.application.capture.state import CaptureState
from erenshor.application.capture.zone_config import (
    CONFIG_RELATIVE_PATH,
    capture_variants,
    get_zone_keys,
    load_zone_config,
)
from erenshor.cli.preconditions.base import PreconditionResult


def capture_config(context: dict[str, Any]) -> PreconditionResult:
    """Require a readable zone configuration and a valid zone selection."""
    path = Path(context["maps_source_dir"]) / CONFIG_RELATIVE_PATH
    try:
        config = load_zone_config(path)
        selected = get_zone_keys(config, context.get("zones"))
        for zone in selected:
            capture_variants(zone, config[zone])
    except (OSError, ValueError, TypeError, KeyError) as error:
        return PreconditionResult(False, "capture_config", f"Cannot use zone configuration {path}", str(error))
    return PreconditionResult(True, "capture_config", f"Zone configuration: {path}")


def captured_masters(context: dict[str, Any]) -> PreconditionResult:
    """Require every selected master before a re-tiling run replaces any tiles."""
    path = Path(context["maps_source_dir"]) / CONFIG_RELATIVE_PATH
    try:
        config = load_zone_config(path)
        state = CaptureState.load(Path(context["repo_root"]))
        missing = []
        for zone in get_zone_keys(config, context.get("zones")):
            for variant in capture_variants(zone, config[zone]):
                record = state.get_variant_state(zone, variant)
                master = (
                    Path(context["repo_root"]) / record["masterPath"] if record and record.get("masterPath") else None
                )
                if master is None or not master.is_file():
                    missing.append(f"{zone}/{variant}: {master or 'no captured master in the capture state'}")
    except (OSError, ValueError, TypeError, KeyError) as error:
        return PreconditionResult(False, "captured_masters", "Cannot inspect capture masters", str(error))
    if missing:
        return PreconditionResult(False, "captured_masters", "Capture masters missing", "\n".join(missing))
    return PreconditionResult(True, "captured_masters", "Capture masters available")
