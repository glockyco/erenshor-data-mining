"""Renderer protocol (interface for template rendering)."""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["TemplateRenderer"]


class TemplateRenderer(Protocol):
    """Protocol for rendering templates."""

    def render(self, template_path: str, *, ctx: Any) -> str:
        """Render a template with the given context."""
        ...
