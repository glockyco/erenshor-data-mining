"""Domain-specific exception hierarchy.

Custom exceptions for clear error handling and propagation throughout the
application. All exceptions inherit from ErenShorWikiError for easy catching.

Design principles:
- Exceptions bubble up, never silenced
- Clear messages indicate what went wrong and why
- Domain exceptions separate from Python built-ins
- Use specific exceptions for specific failures
"""

from __future__ import annotations

__all__ = [
    "ErenShorWikiError",
    "DatabaseError",
    "ValidationError",
    "WikiAPIError",
    "RegistryError",
    "JunctionEnrichmentError",
    "ConfigurationError",
]


class ErenShorWikiError(Exception):
    """Base exception for all erenshor-wiki errors.

    All custom exceptions inherit from this for easy catching of
    application-specific errors.

    Example:
        try:
            repository.get_item(item_id)
        except ErenShorWikiError as e:
            logger.error(f"Application error: {e}")
    """

    pass


class DatabaseError(ErenShorWikiError):
    """Database operation failed.

    Raised when database queries fail, connections drop, or data is
    malformed/missing from database.

    Example:
        raise DatabaseError("Failed to query Items table: connection timeout")
    """

    pass


class ValidationError(ErenShorWikiError):
    """Content validation failed.

    Raised when generated content violates validation rules (missing
    required fields, malformed templates, etc.).

    Example:
        raise ValidationError("Missing required field 'item_name' in template")
    """

    pass


class WikiAPIError(ErenShorWikiError):
    """Wiki API request failed.

    Raised when MediaWiki API calls fail (authentication, upload, fetch).

    Example:
        raise WikiAPIError("Failed to upload page: 403 Forbidden")
    """

    pass


class RegistryError(ErenShorWikiError):
    """Registry operation failed.

    Raised when entity-to-page mapping fails, duplicate mappings found,
    or registry file is corrupted.

    Example:
        raise RegistryError("Entity item:123 already mapped to different page")
    """

    pass


class JunctionEnrichmentError(ErenShorWikiError):
    """Junction table enrichment failed.

    Raised when junction table queries fail or return malformed data.
    This indicates a problem with the database schema or data integrity.

    Example:
        raise JunctionEnrichmentError(
            "CraftingMaterials table missing for item_id=123"
        )
    """

    pass


class ConfigurationError(ErenShorWikiError):
    """Configuration is invalid or missing.

    Raised when required configuration values are missing, invalid,
    or conflicting.

    Example:
        raise ConfigurationError("WIKI_API_URL not set in environment")
    """

    pass
