"""Precondition checks for interactive maps build and deploy commands."""

from __future__ import annotations

import json
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


def no_static_database_files(context: dict[str, Any]) -> PreconditionResult:
    """Check that no SQLite file or link remains among the static assets.

    The site publishes the database from a prerendered route. A static copy,
    such as the link that earlier versions created at static/db, would shadow
    that route in the dev server and collide with it in the build.
    """
    static_dir = Path(context["maps_source_dir"]) / "static"
    stale = sorted(static_dir.rglob("*.sqlite")) if static_dir.is_dir() else []
    if stale:
        return PreconditionResult(
            passed=False,
            check_name="no_static_database_files",
            message="A database file remains in the maps static assets",
            detail="Delete " + ", ".join(str(path) for path in stale),
        )

    return PreconditionResult(
        passed=True,
        check_name="no_static_database_files",
        message="No database file in the maps static assets",
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

    login_hint = (
        "Set CLOUDFLARE_API_TOKEN (+ CLOUDFLARE_ACCOUNT_ID when required) "
        f"or run `pnpm -C {maps_source_dir} exec wrangler login`."
    )
    if shutil.which("pnpm") is None:
        return PreconditionResult(
            passed=False,
            check_name="cloudflare_auth_configured",
            message="Cannot check the wrangler login: pnpm not found on PATH",
            detail=f"The Nix development shell provides pnpm. {login_hint}",
        )

    # Plain `wrangler whoami` exits 0 even when nobody is logged in. With
    # --json it exits non-zero and reports loggedIn false.
    try:
        result = subprocess.run(
            ["pnpm", "exec", "wrangler", "whoami", "--json"],
            cwd=maps_source_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return PreconditionResult(
            passed=False,
            check_name="cloudflare_auth_configured",
            message="Could not run `wrangler whoami`",
            detail=f"{error}. {login_hint}",
        )

    if result.returncode == 0 and _wrangler_logged_in(result.stdout):
        return PreconditionResult(
            passed=True,
            check_name="cloudflare_auth_configured",
            message="Cloudflare wrangler login configured",
        )

    output = (result.stderr.strip() or result.stdout.strip()).splitlines()
    last_line = output[-1] if output else "no output"
    return PreconditionResult(
        passed=False,
        check_name="cloudflare_auth_configured",
        message="Cloudflare authentication not configured",
        detail=f"`wrangler whoami --json` exited {result.returncode}: {last_line}. {login_hint}",
    )


def _wrangler_logged_in(stdout: str) -> bool:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    return isinstance(report, dict) and report.get("loggedIn") is True
