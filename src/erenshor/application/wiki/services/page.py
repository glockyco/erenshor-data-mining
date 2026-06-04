"""Operation result model for wiki fetch/generate/deploy."""

from dataclasses import dataclass


@dataclass
class OperationResult:
    """Result of a wiki operation (fetch/generate/deploy).

    Attributes:
        total: Total number of pages processed.
        succeeded: Number of pages successfully processed.
        failed: Number of pages that failed to process.
        skipped: Number of pages skipped (e.g., no changes needed).
        warnings: List of warning messages.
        errors: List of error messages.
    """

    total: int
    succeeded: int
    failed: int
    skipped: int
    warnings: list[str]
    errors: list[str]

    def has_warnings(self) -> bool:
        """Check if result has warnings."""
        return len(self.warnings) > 0

    def has_errors(self) -> bool:
        """Check if result has errors."""
        return len(self.errors) > 0
