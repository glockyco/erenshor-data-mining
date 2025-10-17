"""Base entity model for all game entities.

This module provides the base class for all domain entities in the Erenshor data mining system.
Domain entities represent game data structures and are validated using Pydantic.
"""

from pydantic import BaseModel, ConfigDict


class BaseEntity(BaseModel):
    """Base class for all game entity models.

    Provides common functionality for domain entities including:
    - Pydantic validation and serialization
    - Strict type checking
    - Immutable after creation (frozen)

    All entity subclasses should inherit from this base class to ensure
    consistent validation and behavior across the domain layer.
    """

    model_config = ConfigDict(
        strict=True,  # Strict type coercion
        frozen=False,  # Allow mutation (needed for ORM operations)
        validate_assignment=True,  # Validate field assignments
        arbitrary_types_allowed=True,  # Allow custom types
        populate_by_name=True,  # Allow both field name and alias for population
    )
