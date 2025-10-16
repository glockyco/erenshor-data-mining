"""Jinja2 template engine for wiki content generation."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined


def _duration(value: float | int) -> str:
    """Format duration in seconds to human-readable string."""
    if value <= 0:
        return ""
    minutes, seconds = divmod(int(value), 60)
    if minutes and seconds:
        return f"{minutes} minute{'s' if minutes != 1 else ''} {seconds} second{'s' if seconds != 1 else ''}"
    if minutes:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{seconds} second{'s' if seconds != 1 else ''}"


def _percent(value: float) -> str:
    """Format float as percentage string."""
    return f"{value:.0f}%"


def _nonempty(value: str | None) -> bool:
    """Check if string value is non-empty after stripping."""
    return bool(value and value.strip())


def _escape_page(value: str) -> str:
    """Sanitize page name for wiki/filesystem use."""
    return value.replace(":", "").strip()


def build_env() -> Environment:
    """Build Jinja2 environment with custom filters.

    Loads templates from the installed package and adds custom filters
    for wiki content formatting.
    """
    env = Environment(
        loader=PackageLoader("erenshor", "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(
        duration=_duration,
        percent=_percent,
        nonempty=_nonempty,
        escape_page=_escape_page,
    )
    return env


# Singleton environment instance
_env: Environment | None = None


def render_template(template_path: str, ctx: Any) -> str:
    """Render a template with the given context.

    Uses a singleton environment instance for efficiency.

    Args:
        template_path: Path to template relative to templates/ directory
        ctx: Context object to pass to template

    Returns:
        Rendered template string
    """
    global _env
    if _env is None:
        _env = build_env()
    template = _env.get_template(template_path)
    return template.render(ctx=ctx)


__all__ = ["build_env", "render_template"]
