"""MediaWiki template parser using mwparserfromhell.

This module provides utilities for parsing and manipulating MediaWiki templates
in wikitext. It wraps the mwparserfromhell library with a clean, type-safe API
designed for the Erenshor wiki data pipeline.

Features:
- Parse wikitext and extract templates by name
- Get/set/delete template parameters
- Generate template strings from data
- Preserve wiki markup structure (comments, formatting, etc.)
- Handle nested templates
- Type-safe interface with comprehensive error handling

Example:
    >>> parser = TemplateParser()
    >>> code = parser.parse("{{Item|name=Sword|damage=10}}")
    >>> templates = parser.find_templates(code, ["Item"])
    >>> params = parser.get_params(templates[0])
    >>> print(params)
    {'name': 'Sword', 'damage': '10'}

    >>> # Update parameter
    >>> parser.set_param(templates[0], "damage", "15")
    >>> print(parser.render(code))
    {{Item|name=Sword|damage=15}}

    >>> # Generate new template
    >>> template_str = parser.generate_template("Item", {"name": "Shield", "defense": "20"})
    >>> print(template_str)
    {{Item
    |name=Shield
    |defense=20
    }}
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import mwparserfromhell as mw
from loguru import logger

if TYPE_CHECKING:
    from mwparserfromhell.nodes import Template
    from mwparserfromhell.wikicode import Wikicode


class TemplateParserError(Exception):
    """Base exception for template parser errors.

    This is the parent exception for all template parsing failures.
    """

    pass


class TemplateNotFoundError(TemplateParserError):
    """Raised when a template is not found in wikitext.

    This occurs when searching for a template by name that doesn't exist
    on the page.
    """

    pass


class InvalidWikitextError(TemplateParserError):
    """Raised when wikitext cannot be parsed.

    This occurs when the input text is malformed or cannot be processed
    by mwparserfromhell.
    """

    pass


class TemplateParser:
    """Parser for MediaWiki templates using mwparserfromhell.

    This class provides a high-level API for working with MediaWiki templates,
    abstracting away the details of mwparserfromhell's AST manipulation.

    All methods preserve the structure and formatting of the wikitext,
    including comments, whitespace, and other markup.

    Example:
        >>> parser = TemplateParser()
        >>> wikitext = "{{Item|name=Sword|damage=10}}"
        >>> code = parser.parse(wikitext)
        >>> templates = parser.find_templates(code, ["Item"])
        >>> params = parser.get_params(templates[0])
        >>> print(params)
        {'name': 'Sword', 'damage': '10'}
    """

    def parse(self, wikitext: str) -> "Wikicode":
        """Parse wikitext into mwparserfromhell AST.

        Args:
            wikitext: MediaWiki wikitext to parse.

        Returns:
            Wikicode object (mwparserfromhell AST).

        Raises:
            InvalidWikitextError: If wikitext cannot be parsed.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword}}")
            >>> print(type(code).__name__)
            Wikicode
        """
        try:
            logger.debug(f"Parsing wikitext ({len(wikitext)} characters)")
            return mw.parse(wikitext)
        except Exception as e:
            logger.error(f"Failed to parse wikitext: {e}")
            raise InvalidWikitextError(f"Failed to parse wikitext: {e}") from e

    def find_templates(self, code: "Wikicode", names: Sequence[str]) -> list["Template"]:
        """Find all templates matching any of the given names.

        Template name matching is case-insensitive and strips whitespace.

        Args:
            code: Parsed wikicode object from parse().
            names: List of template names to search for (e.g., ["Item", "Weapon"]).

        Returns:
            List of template objects (mwparserfromhell Template nodes).

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword}} {{Weapon|damage=10}}")
            >>> item_templates = parser.find_templates(code, ["Item"])
            >>> print(len(item_templates))
            1
            >>> weapon_templates = parser.find_templates(code, ["Weapon"])
            >>> print(len(weapon_templates))
            1
            >>> all_templates = parser.find_templates(code, ["Item", "Weapon"])
            >>> print(len(all_templates))
            2
        """
        target = {n.lower().strip() for n in names}
        templates = [t for t in code.filter_templates() if str(t.name).strip().lower() in target]
        logger.debug(f"Found {len(templates)} templates matching {names}")
        return templates

    def find_template(self, code: "Wikicode", names: Sequence[str]) -> "Template":
        """Find first template matching any of the given names.

        Convenience method that returns a single template instead of a list.

        Args:
            code: Parsed wikicode object from parse().
            names: List of template names to search for.

        Returns:
            First matching template object.

        Raises:
            TemplateNotFoundError: If no matching template is found.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword}}")
            >>> template = parser.find_template(code, ["Item"])
            >>> params = parser.get_params(template)
            >>> print(params['name'])
            Sword
        """
        templates = self.find_templates(code, names)
        if not templates:
            logger.error(f"Template not found: {names}")
            raise TemplateNotFoundError(f"No template found matching: {names}")
        return templates[0]

    def get_params(self, template: "Template") -> dict[str, str]:
        """Extract all parameters from a template as key-value pairs.

        Parameter names and values are stripped of whitespace.

        Args:
            template: Template object from find_templates() or find_template().

        Returns:
            Dictionary mapping parameter names to values (both as strings).

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword|damage=10|level=5}}")
            >>> template = parser.find_template(code, ["Item"])
            >>> params = parser.get_params(template)
            >>> print(params)
            {'name': 'Sword', 'damage': '10', 'level': '5'}
        """
        params: dict[str, str] = {}
        for param in template.params:
            name = str(param.name).strip()
            value = str(param.value).strip()
            params[name] = value
        logger.debug(f"Extracted {len(params)} parameters from template")
        return params

    def get_param(self, template: "Template", name: str, default: str | None = None) -> str | None:
        """Get value of a single template parameter.

        Args:
            template: Template object from find_templates() or find_template().
            name: Parameter name to retrieve.
            default: Default value if parameter doesn't exist.

        Returns:
            Parameter value as string, or default if not found.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword|damage=10}}")
            >>> template = parser.find_template(code, ["Item"])
            >>> print(parser.get_param(template, "name"))
            Sword
            >>> print(parser.get_param(template, "level", "1"))
            1
            >>> print(parser.get_param(template, "missing"))
            None
        """
        params = self.get_params(template)
        return params.get(name, default)

    def set_param(self, template: "Template", name: str, value: str) -> None:
        """Set or update a template parameter.

        If the parameter exists, updates its value. If not, adds it.

        Args:
            template: Template object to modify.
            name: Parameter name to set.
            value: Parameter value to set.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword|damage=10}}")
            >>> template = parser.find_template(code, ["Item"])
            >>> parser.set_param(template, "damage", "15")
            >>> parser.set_param(template, "level", "5")  # Add new param
            >>> print(parser.render(code))
            {{Item|name=Sword|damage=15|level=5}}
        """
        try:
            # Check if parameter exists
            if template.has(name):
                # Update existing parameter
                template.get(name).value = value
                logger.debug(f"Updated parameter: {name}={value}")
            else:
                # Add new parameter
                template.add(name, value)
                logger.debug(f"Added parameter: {name}={value}")
        except Exception as e:
            logger.error(f"Failed to set parameter {name}={value}: {e}")
            raise TemplateParserError(f"Failed to set parameter: {e}") from e

    def remove_param(self, template: "Template", name: str) -> None:
        """Remove a parameter from a template.

        If the parameter doesn't exist, does nothing (idempotent).

        Args:
            template: Template object to modify.
            name: Parameter name to remove.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword|damage=10|level=5}}")
            >>> template = parser.find_template(code, ["Item"])
            >>> parser.remove_param(template, "level")
            >>> print(parser.render(code))
            {{Item|name=Sword|damage=10}}
        """
        try:
            if template.has(name):
                template.remove(name)
                logger.debug(f"Removed parameter: {name}")
            else:
                logger.debug(f"Parameter not found, nothing to remove: {name}")
        except Exception as e:
            logger.error(f"Failed to remove parameter {name}: {e}")
            raise TemplateParserError(f"Failed to remove parameter: {e}") from e

    def replace_template(self, code: "Wikicode", old_template: "Template", new_content: str) -> str:
        """Replace a template with new content.

        Args:
            code: Parsed wikicode object.
            old_template: Template object to replace.
            new_content: New wikitext content (can be template, text, or empty).

        Returns:
            Updated wikitext as string.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword}} is a weapon")
            >>> template = parser.find_template(code, ["Item"])
            >>> result = parser.replace_template(code, template, "{{Weapon|name=Sword|damage=10}}")
            >>> print(result)
            {{Weapon|name=Sword|damage=10}} is a weapon
        """
        try:
            code.replace(old_template, new_content)
            logger.debug(f"Replaced template with new content ({len(new_content)} characters)")
            return str(code)
        except Exception as e:
            logger.error(f"Failed to replace template: {e}")
            raise TemplateParserError(f"Failed to replace template: {e}") from e

    def remove_template(self, code: "Wikicode", template: "Template") -> str:
        """Remove a template from wikitext.

        Convenience method equivalent to replace_template(code, template, "").

        Args:
            code: Parsed wikicode object.
            template: Template object to remove.

        Returns:
            Updated wikitext as string.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword}} is a weapon")
            >>> template = parser.find_template(code, ["Item"])
            >>> result = parser.remove_template(code, template)
            >>> print(result)
             is a weapon
        """
        return self.replace_template(code, template, "")

    def generate_template(
        self,
        name: str,
        params: Mapping[str, str | int | float | bool | None],
        inline: bool = False,
    ) -> str:
        """Generate a template string from name and parameters.

        Args:
            name: Template name (e.g., "Item", "Weapon").
            params: Dictionary of parameter name-value pairs.
            inline: If True, generate inline format. If False, multi-line format.

        Returns:
            Generated template as wikitext string.

        Example:
            >>> parser = TemplateParser()
            >>> # Multi-line format (default)
            >>> template = parser.generate_template("Item", {"name": "Sword", "damage": 10})
            >>> print(template)
            {{Item
            |name=Sword
            |damage=10
            }}

            >>> # Inline format
            >>> template = parser.generate_template("Item", {"name": "Sword"}, inline=True)
            >>> print(template)
            {{Item|name=Sword}}
        """
        # Convert all values to strings
        str_params = {k: self._value_to_string(v) for k, v in params.items()}

        if inline:
            param_str = "|".join(f"{k}={v}" for k, v in str_params.items())
            result = f"{{{{{name}|{param_str}}}}}" if param_str else f"{{{{{name}}}}}"
        elif str_params:
            lines = [f"{{{{{name}"]
            for k, v in str_params.items():
                lines.append(f"|{k}={v}")
            lines.append("}}")
            result = "\n".join(lines)
        else:
            result = "{{" + name + "\n}}"

        logger.debug(f"Generated template: {name} with {len(str_params)} parameters")
        return result

    def render(self, code: "Wikicode") -> str:
        """Render wikicode object back to wikitext string.

        This is the inverse of parse() - converts the AST back to text.

        Args:
            code: Wikicode object to render.

        Returns:
            Wikitext as string.

        Example:
            >>> parser = TemplateParser()
            >>> code = parser.parse("{{Item|name=Sword}}")
            >>> # Modify code...
            >>> wikitext = parser.render(code)
        """
        return str(code)

    def _value_to_string(self, value: str | int | float | bool | None) -> str:
        """Convert parameter value to string.

        Args:
            value: Parameter value of various types.

        Returns:
            String representation suitable for wiki templates.

        Note:
            None values are converted to empty strings. In MediaWiki templates,
            there is a difference between a missing parameter and an explicitly
            empty parameter (|param=), but this method treats None as explicitly
            empty. This is intentional for template generation where we want to
            explicitly set parameters to empty values.
        """
        if value is None:
            # MediaWiki treats missing params and empty params differently.
            # Converting None to empty string means the parameter will be
            # explicitly set to empty (|param=) rather than omitted entirely.
            logger.debug("Converting None to empty string - parameter will be explicitly empty")
            return ""
        if isinstance(value, bool):
            return "yes" if value else "no"
        return str(value)
