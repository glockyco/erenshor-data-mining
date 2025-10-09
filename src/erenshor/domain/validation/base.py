"""Base protocols and types for content validation.

Validators check wiki pages for structural correctness and completeness,
operating on generated content before it's written to files. Violations
are categorized by severity and can be used for reporting or to block writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from erenshor.registry.core import WikiPage

__all__ = ["BaseContentValidator", "ContentValidator", "ValidationResult", "Violation"]


@dataclass(frozen=True)
class Violation:
    """A single validation violation.

    Categorized by severity:
    - error: Structural problems that make content invalid (blocks write)
    - warning: Issues that should be reviewed but don't block write

    Attributes:
        field: Field or section where violation occurred (e.g., "infobox", "sell")
        message: Human-readable description of the violation
        severity: "error" or "warning"
    """

    field: str
    message: str
    severity: Literal["error", "warning"]


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a wiki page.

    Attributes:
        passed: True if no errors (warnings don't fail validation)
        violations: List of all violations found (errors + warnings)
    """

    passed: bool
    violations: list[Violation] = field(default_factory=list)

    @property
    def errors(self) -> list[Violation]:
        """Get only error-level violations."""
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[Violation]:
        """Get only warning-level violations."""
        return [v for v in self.violations if v.severity == "warning"]

    @property
    def error_count(self) -> int:
        """Count of error-level violations."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Count of warning-level violations."""
        return len(self.warnings)


class ContentValidator(Protocol):
    """Protocol for content validators.

    Validators check wiki pages for correctness, enforcing rules like:
    - Template presence and uniqueness (exactly one infobox)
    - Required fields (sell value, type, etc.)
    - Structural rules (weapons must have fancy tables)
    - Link formats (proper wikilinks)

    Commands can:
    - Skip validation entirely (--no-validate)
    - Validate during update (default)
    - Only validate without writing (--validate-only)

    Example:
        ```python
        class ItemValidator:
            def validate(
                self,
                page: WikiPage,
                content: str
            ) -> ValidationResult:
                violations = []

                code = mwparserfromhell.parse(content)
                infoboxes = find_item_templates(code)
                if not infoboxes:
                    violations.append(
                        Violation("infobox", "No infobox found", "error")
                    )

                if infoboxes and not get_param(infoboxes[0], "sell"):
                    violations.append(
                        Violation("sell", "Sell value missing", "warning")
                    )

                passed = all(v.severity != "error" for v in violations)
                return ValidationResult(passed=passed, violations=violations)
        ```

    Notes:
        - Validators operate on rendered content (post-transformation)
        - Violations should be specific and actionable
        - Errors block writes, warnings are informational
    """

    def validate(self, page: WikiPage, content: str) -> ValidationResult:
        """Validate wiki page content.

        Args:
            page: Wiki page metadata (title, entities, etc.)
            content: Rendered wiki page text to validate

        Returns:
            ValidationResult with pass/fail status and violations

        Notes:
            - Validators should not raise exceptions for validation failures
            - Parse errors should be returned as violations
            - Unexpected errors (bugs) should propagate as exceptions
        """
        ...


class BaseContentValidator:
    """Base class for content validators with common helper methods.

    Provides shared parsing and violation creation logic that all validators
    need, eliminating duplication across ItemValidator, CharacterValidator, etc.
    """

    def _parse_page(self, content: str) -> Any:
        """Parse wikitext content using mwparserfromhell.

        Args:
            content: Wikitext string to parse

        Returns:
            Wikicode AST object
        """
        import mwparserfromhell

        return mwparserfromhell.parse(content)

    def _find_template(self, wikicode: Any, name: str) -> Any | None:
        """Find template by name in parsed wikitext.

        Args:
            wikicode: mwparserfromhell Wikicode object
            name: Template name to search for (case-insensitive)

        Returns:
            Template object if found, None otherwise
        """
        for template in wikicode.filter_templates():
            if template.name.strip().lower() == name.lower():
                return template
        return None

    def _create_violation(
        self,
        field: str,
        message: str,
        severity: Literal["error", "warning"] = "error",
    ) -> Violation:
        """Create a validation violation.

        Args:
            field: Field or section where violation occurred
            message: Human-readable description
            severity: "error" or "warning"

        Returns:
            Violation object
        """
        return Violation(field=field, message=message, severity=severity)
