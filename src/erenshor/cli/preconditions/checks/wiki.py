"""Preflight checks for publishing wiki content."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from erenshor.cli.preconditions.base import PreconditionResult
from erenshor.cli.preconditions.checks.database import database_exists, database_has_items, database_valid
from erenshor.cli.preconditions.checks.inputs import option_path


def wiki_endpoint(context: dict[str, Any]) -> PreconditionResult:
    """Require an HTTP endpoint before starting a MediaWiki API read."""
    if context.get("fixture_dir") is not None:
        return PreconditionResult(True, "wiki_endpoint", "Recorded wiki fixtures replace the live endpoint")
    url = context["config"].global_.mediawiki.api_url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return PreconditionResult(False, "wiki_endpoint", f"MediaWiki API URL invalid: {url!r}")
    return PreconditionResult(True, "wiki_endpoint", f"MediaWiki API URL: {url}")


def interface_admin_credentials(context: dict[str, Any]) -> PreconditionResult:
    """Require the dedicated interface account, not a normal bot fallback."""
    wiki = context["config"].global_.mediawiki
    if wiki.interface_username.strip() and wiki.interface_password:
        return PreconditionResult(True, "interface_admin_credentials", "Interface administrator configured")
    return PreconditionResult(
        False,
        "interface_admin_credentials",
        "Dedicated interface-admin credentials not configured",
        "Set interface_username and interface_password in .erenshor/config.local.toml.",
    )


def wiki_deploy_inputs(context: dict[str, Any]) -> PreconditionResult:
    """A directory upload needs its directory, generated storage needs its database."""
    if context.get("from_dir"):
        return option_path("from_dir", kind="directory")(context)
    for check in (database_exists, database_valid, database_has_items):
        result = check(context)
        if not result.passed:
            return result
    return PreconditionResult(True, "wiki_deploy_inputs", "Generated article inputs available")
