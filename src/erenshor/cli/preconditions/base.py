"""Base types for precondition checking system.

This module defines the core types used by the precondition system:
- PreconditionResult: Result of a single precondition check
- PreconditionCheck: Type alias for check functions
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class PreconditionResult:
    """Result of a precondition check.

    Attributes:
        passed: Whether the check passed.
        check_name: Name of the check function (for identification).
        message: Short message describing the result.
        detail: Optional detailed information (e.g., error hints).
    """

    passed: bool
    check_name: str
    message: str
    detail: str = ""

    def __str__(self) -> str:
        """Format result for display.

        Returns:
            Formatted string with ✓ or ✗ prefix and message.
            If detail is present, it's included on the next line.
        """
        symbol = "✓" if self.passed else "✗"
        result = f"{symbol} {self.message}"
        if self.detail:
            # Indent detail lines
            detail_lines = self.detail.split("\n")
            indented = "\n  ".join(detail_lines)
            result += f"\n  {indented}"
        return result


# Type alias for precondition check functions
# Check functions take a context dict and return a PreconditionResult
PreconditionCheck = Callable[[dict[str, Any]], PreconditionResult]
