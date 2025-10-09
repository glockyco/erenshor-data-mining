"""Link resolution system using registry."""

from __future__ import annotations

from typing import Optional

from erenshor.registry.core import EntityRef, WikiRegistry

__all__ = ["RegistryLinkResolver"]


class RegistryLinkResolver:
    """Generate wiki links using registry."""

    def __init__(self, registry: WikiRegistry):
        self.registry = registry

    def resolve_item_title(
        self, resource_name: str, fallback_name: str, db_id: Optional[str] = None
    ) -> str:
        """Resolve item title using registry."""
        from .core import EntityType

        entity = EntityRef(
            entity_type=EntityType.ITEM,
            db_id=db_id,
            db_name=fallback_name,
            resource_name=resource_name,
        )
        page = self.registry.resolve_entity(entity)
        return page.title if page else fallback_name

    def resolve_character_title(self, stable_id: str, fallback_name: str) -> str:
        """Resolve character title using registry."""
        from .core import EntityType

        entity = EntityRef(
            entity_type=EntityType.CHARACTER,
            db_id=None,
            db_name=fallback_name,
            resource_name=stable_id,
        )
        page = self.registry.resolve_entity(entity)
        return page.title if page else fallback_name

    def resolve_quest_title(self, db_name: str, fallback_name: str) -> str:
        """Resolve quest title using registry."""
        from .core import EntityType

        entity = EntityRef(
            entity_type=EntityType.QUEST,
            db_id=None,
            db_name=fallback_name,
            resource_name=db_name,
        )
        page = self.registry.resolve_entity(entity)
        return page.title if page else fallback_name

    def resolve_spell_title(self, resource_name: str, fallback_name: str) -> str:
        """Resolve ability (spell/skill) title using registry.

        Tries SPELL first, then SKILL, then falls back to name.
        This handles the unified wiki namespace while preserving backend distinction.
        """
        from .core import EntityType

        # Try spell first
        spell_entity = EntityRef(
            entity_type=EntityType.SPELL,
            db_id=None,
            db_name=fallback_name,
            resource_name=resource_name,
        )
        page = self.registry.resolve_entity(spell_entity)
        if page:
            return page.title

        # Try skill
        skill_entity = EntityRef(
            entity_type=EntityType.SKILL,
            db_id=None,
            db_name=fallback_name,
            resource_name=resource_name,
        )
        page = self.registry.resolve_entity(skill_entity)
        if page:
            return page.title

        # Fallback
        return fallback_name

    def resolve_faction_title(self, refname: str, fallback_name: str) -> str:
        """Resolve faction title using registry."""
        from .core import EntityType

        entity = EntityRef(
            entity_type=EntityType.FACTION,
            db_id=None,
            db_name=fallback_name,
            resource_name=refname,
        )
        page = self.registry.resolve_entity(entity)
        return page.title if page else fallback_name

    def item_link(
        self,
        resource_name: str,
        fallback_name: str,
        db_id: Optional[str] = None,
        display_text: Optional[str] = None,
    ) -> str:
        """Generate {{ItemLink|...}} for an item.

        Args:
            resource_name: Item resource name for lookup
            fallback_name: Display name if not in registry
            db_id: Database ID for precise lookup
            display_text: Optional display text (if different from resolved title)

        Returns:
            {{ItemLink|PageTitle|text=DisplayText}} if display differs
            {{ItemLink|PageTitle}} otherwise
        """
        title = self.resolve_item_title(resource_name, fallback_name, db_id)
        if display_text and display_text != title:
            return f"{{{{ItemLink|{title}|text={display_text}}}}}"
        return f"{{{{ItemLink|{title}}}}}"

    def ability_link(
        self, resource_name: str, fallback_name: str, display_text: Optional[str] = None
    ) -> str:
        """Generate {{AbilityLink|...}} for an ability (spell/skill).

        Tries SPELL first, then SKILL. Both map to unified {{AbilityLink}} template.

        Args:
            resource_name: Ability resource name for lookup
            fallback_name: Display name if not in registry
            display_text: Optional display text (if different from resolved title)

        Returns:
            {{AbilityLink|PageTitle|text=DisplayText}} if display differs
            {{AbilityLink|PageTitle}} otherwise
        """
        from .core import EntityType

        # Try spell first
        spell_entity = EntityRef(
            entity_type=EntityType.SPELL,
            db_id=None,
            db_name=fallback_name,
            resource_name=resource_name,
        )
        page = self.registry.resolve_entity(spell_entity)
        if page:
            title = page.title
            if display_text and display_text != title:
                return f"{{{{AbilityLink|{title}|text={display_text}}}}}"
            return f"{{{{AbilityLink|{title}}}}}"

        # Try skill
        skill_entity = EntityRef(
            entity_type=EntityType.SKILL,
            db_id=None,
            db_name=fallback_name,
            resource_name=resource_name,
        )
        page = self.registry.resolve_entity(skill_entity)
        if page:
            title = page.title
            if display_text and display_text != title:
                return f"{{{{AbilityLink|{title}|text={display_text}}}}}"
            return f"{{{{AbilityLink|{title}}}}}"

        # Fallback
        return f"{{{{AbilityLink|{fallback_name}}}}}"

    def character_link(
        self, entity_ref: EntityRef, display_text: Optional[str] = None
    ) -> str:
        """Generate standard MediaWiki link for a character.

        Uses [[Page]] or [[Page|Display]] syntax, consistent with zones and factions.

        Args:
            entity_ref: Character EntityRef
            display_text: Optional display text (if different from resolved title)

        Returns:
            [[PageTitle|DisplayText]] if display differs
            [[PageTitle]] otherwise
        """
        page = self.registry.resolve_entity(entity_ref)
        title = page.title if page else entity_ref.db_name

        # Use registry display name if no explicit display_text provided
        if not display_text:
            display_text = self.registry.get_display_name(entity_ref)

        if display_text and display_text != title:
            return f"[[{title}|{display_text}]]"
        return f"[[{title}]]"

    def wiki_link(self, entity: EntityRef, display_text: Optional[str] = None) -> str:
        """Generate [[Page|Display]] or [[Page]] link."""
        page = self.registry.resolve_entity(entity)
        title = page.title if page else entity.db_name

        if display_text and display_text != title:
            return f"[[{title}|{display_text}]]"
        return f"[[{title}]]"
