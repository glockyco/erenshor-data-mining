"""Base class for template generators with Jinja2 template support.

This module provides the abstract base class for all template generators. Template
generators are responsible for generating individual MediaWiki template/infobox wikitext
for a single game entity.

Key responsibilities:
- Load and render Jinja2 templates
- Format category tags
- Normalize wikitext output
- Provide common utilities for subclasses

Design:
- Generators handle SINGLE entities only (multi-entity logic is in WikiService)
- Template-driven (business logic in Python, markup in Jinja2)
- Type-safe (full Pydantic validation)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger


class TemplateGeneratorError(Exception):
    """Base exception for template generator errors."""

    pass


class TemplateNotFoundError(TemplateGeneratorError):
    """Raised when a Jinja2 template file cannot be found."""

    pass


class TemplateRenderError(TemplateGeneratorError):
    """Raised when template rendering fails."""

    pass


class TemplateGeneratorBase(ABC):
    """Abstract base class for template generators.

    Provides common functionality for rendering Jinja2 templates and formatting
    wikitext. Subclasses implement entity-specific template generation logic.

    Template generators handle SINGLE entities only. Multi-entity page assembly
    is handled by WikiService.

    The template system expects:
    - Templates in src/erenshor/application/generators/templates/
    - Context data as simple dicts (not Pydantic models)
    - MediaWiki template syntax in Jinja2 templates

    Example:
        >>> class ItemTemplateGenerator(TemplateGeneratorBase):
        ...     def generate_template(self, item: Item, page_title: str) -> str:
        ...         context = {"name": item.item_name, "level": item.item_level}
        ...         wikitext = self.render_template("item.jinja2", context)
        ...         categories = self.format_category_tags(["Items", "Equipment"])
        ...         return wikitext + "\\n" + categories
    """

    def __init__(self) -> None:
        """Initialize template generator with Jinja2 environment."""
        self._template_dir = self._get_template_directory()
        self._jinja_env = self._create_jinja_environment()
        logger.debug(f"Initialized {self.__class__.__name__} with template dir: {self._template_dir}")

    def _get_template_directory(self) -> Path:
        """Get path to templates directory.

        Returns:
            Path to templates directory (src/erenshor/application/generators/templates/)

        Raises:
            TemplateNotFoundError: If templates directory doesn't exist.
        """
        # Templates are in same directory as this module
        template_dir = Path(__file__).parent / "templates"

        if not template_dir.exists():
            raise TemplateNotFoundError(
                f"Template directory not found: {template_dir}. Expected templates/ directory in generators module."
            )

        return template_dir

    def _create_jinja_environment(self) -> Environment:
        """Create Jinja2 environment for template rendering.

        Returns:
            Configured Jinja2 Environment instance.
        """
        env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            # Preserve newlines and whitespace for wiki markup
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
            # Disable autoescape (we're generating wikitext, not HTML)
            autoescape=False,
        )

        logger.debug("Created Jinja2 environment for template rendering")
        return env

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template with given context.

        Args:
            template_name: Template filename (e.g., "item.jinja2")
            context: Template context variables as dict

        Returns:
            Rendered template as string

        Raises:
            TemplateNotFoundError: If template file doesn't exist
            TemplateRenderError: If rendering fails

        Example:
            >>> context = {"name": "Sword", "damage": 10}
            >>> wikitext = self.render_template("weapon.jinja2", context)
        """
        try:
            template = self._jinja_env.get_template(template_name)
            rendered = template.render(**context)
            logger.debug(f"Rendered template {template_name} ({len(rendered)} characters)")
            return str(rendered)  # Explicitly cast to satisfy mypy
        except Exception as e:
            if "not found" in str(e).lower():
                raise TemplateNotFoundError(f"Template not found: {template_name}") from e
            raise TemplateRenderError(f"Failed to render template {template_name}: {e}") from e

    def format_category_tags(self, categories: list[str]) -> str:
        """Format category tags for MediaWiki.

        Args:
            categories: List of category names (without "Category:" prefix)

        Returns:
            Formatted category tags as wikitext

        Example:
            >>> self.format_category_tags(["Items", "Weapons", "Level 10"])
            "[[Category:Items]]\\n[[Category:Weapons]]\\n[[Category:Level 10]]"

            >>> self.format_category_tags([])
            ""
        """
        if not categories:
            return ""

        tags = [f"[[Category:{cat}]]" for cat in categories]
        return "\n".join(tags)

    def normalize_wikitext(self, wikitext: str) -> str:
        """Normalize wikitext output.

        Performs standard cleanup:
        - Remove trailing whitespace from lines
        - Normalize line endings
        - Remove excessive blank lines (3+ consecutive -> 2)
        - Ensure single trailing newline

        Args:
            wikitext: Raw wikitext string

        Returns:
            Normalized wikitext string

        Example:
            >>> text = "Line 1   \\n\\n\\n\\nLine 2\\n\\n"
            >>> self.normalize_wikitext(text)
            "Line 1\\n\\nLine 2\\n"
        """
        # Remove trailing whitespace from each line
        lines = [line.rstrip() for line in wikitext.splitlines()]

        # Remove excessive blank lines (3+ consecutive -> 2)
        normalized_lines: list[str] = []
        consecutive_blanks = 0

        for line in lines:
            if not line:
                consecutive_blanks += 1
                if consecutive_blanks <= 2:
                    normalized_lines.append(line)
            else:
                consecutive_blanks = 0
                normalized_lines.append(line)

        # Join and ensure single trailing newline
        result = "\n".join(normalized_lines)
        if result and not result.endswith("\n"):
            result += "\n"

        return result

    @abstractmethod
    def generate_template(self, *args: Any, **kwargs: Any) -> str:
        """Generate template wikitext for a single entity.

        Subclasses must implement this to define entity-specific template generation.
        Should return template wikitext (infobox + categories) for ONE entity only.

        Multi-entity page assembly is handled by WikiService, not here.

        Args:
            *args: Entity data (subclass-specific, must be single entity)
            **kwargs: Additional options (e.g., page_title)

        Returns:
            Template wikitext for single entity
        """
        pass
