"""Precondition checks for interactive maps build and deploy commands."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from erenshor.application.maps import build_info
from erenshor.cli.preconditions.base import PreconditionResult


def build_exists(context: dict[str, Any]) -> PreconditionResult:
    """Check that a non-empty maps build directory exists."""
    build_dir = Path(context.get("build_dir", ""))
    if not build_dir.is_dir() or not any(build_dir.iterdir()):
        return PreconditionResult(
            passed=False,
            check_name="build_exists",
            message="Maps build not found",
            detail=f"Run `erenshor maps build` before previewing or deploying. Missing or empty: {build_dir}",
        )

    return PreconditionResult(
        passed=True,
        check_name="build_exists",
        message=f"Maps build exists: {build_dir}",
    )


def build_matches_inputs(context: dict[str, Any]) -> PreconditionResult:
    """Check that the current build sidecar matches maps input hashes."""
    maps_source_dir = Path(context.get("maps_source_dir", ""))
    build_dir = Path(context.get("build_dir", ""))
    database_path = Path(context.get("database_path", ""))

    previous = build_info.read_build_info(build_dir)
    if previous is None:
        return PreconditionResult(
            passed=False,
            check_name="build_matches_inputs",
            message="Maps build provenance not found",
            detail=f"Run `erenshor maps build` to create {build_info.BUILD_INFO_NAME} before previewing or deploying.",
        )

    try:
        current = build_info.compute_input_hashes(maps_source_dir=maps_source_dir, database_path=database_path)
    except build_info.TileInputError as error:
        return PreconditionResult(
            passed=False,
            check_name="build_matches_inputs",
            message="Map tile inputs are incomplete",
            detail=str(error),
        )
    changed = build_info.changed_groups(previous, current)
    if changed:
        changed_list = ", ".join(sorted(changed))
        return PreconditionResult(
            passed=False,
            check_name="build_matches_inputs",
            message="Maps build is stale",
            detail=f"Changed input groups: {changed_list}. Run `erenshor maps build` before previewing or deploying.",
        )

    return PreconditionResult(
        passed=True,
        check_name="build_matches_inputs",
        message="Maps build matches current inputs",
    )


def cloudflare_auth_configured(context: dict[str, Any]) -> PreconditionResult:
    """Check that Cloudflare credentials are available for wrangler deploy."""
    maps_source_dir = Path(context["maps_source_dir"])
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        return PreconditionResult(
            passed=True,
            check_name="cloudflare_auth_configured",
            message="Cloudflare API token configured",
        )

    if shutil.which("pnpm") is not None:
        try:
            result = subprocess.run(
                ["pnpm", "exec", "wrangler", "whoami"],
                cwd=maps_source_dir,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return PreconditionResult(
                    passed=True,
                    check_name="cloudflare_auth_configured",
                    message="Cloudflare wrangler login configured",
                )
        except (OSError, subprocess.SubprocessError):
            pass

    return PreconditionResult(
        passed=False,
        check_name="cloudflare_auth_configured",
        message="Cloudflare authentication not configured",
        detail=(
            "Set CLOUDFLARE_API_TOKEN (+ CLOUDFLARE_ACCOUNT_ID when required) "
            f"or run `pnpm -C {maps_source_dir} exec wrangler login`."
        ),
    )
