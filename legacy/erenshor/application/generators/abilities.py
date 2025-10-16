"""Ability content generator facade.

Provides unified interface for generating spell and skill wiki content.
Delegates to SpellGenerator and SkillGenerator internally.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.engine import Engine

from erenshor.application.generators.base import BaseGenerator, GeneratedContent
from erenshor.application.generators.skills import SkillGenerator
from erenshor.application.generators.spells import SpellGenerator
from erenshor.registry.core import WikiRegistry

__all__ = ["AbilityGenerator"]


class AbilityGenerator(BaseGenerator):
    """Generate ability page content from database.

    Facade that coordinates SpellGenerator and SkillGenerator to provide
    unified interface for CLI and update service.

    Maintains backward compatibility with existing update commands while
    providing proper separation between spells and skills internally.
    """

    def __init__(self) -> None:
        """Initialize ability generator facade."""
        super().__init__()
        self._spell_gen = SpellGenerator()
        self._skill_gen = SkillGenerator()

    def generate(
        self,
        engine: Engine,
        registry: WikiRegistry,
        filter: str | None = None,
    ) -> Iterator[GeneratedContent]:
        """Generate ability content with streaming.

        Delegates to SpellGenerator and SkillGenerator internally.

        Args:
            engine: SQLAlchemy engine for database queries
            registry: Wiki registry for link resolution and page title resolution
            filter: Optional filter string (name or 'id:spell_name') to process specific abilities

        Yields:
            GeneratedContent for each ability (spells first, then skills)
        """
        # Generate all spells
        yield from self._spell_gen.generate(engine, registry, filter)

        # Generate all skills
        yield from self._skill_gen.generate(engine, registry, filter)
