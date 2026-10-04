"""Preflight checks for publishing wiki content."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from erenshor.cli.preconditions.base import PreconditionResult


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
