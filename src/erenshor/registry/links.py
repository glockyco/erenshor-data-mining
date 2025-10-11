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
    ) -> str:
        """Generate {{ItemLink|...}} for an item.

        Args:
            resource_name: Item resource name for lookup
            fallback_name: Display name if not in registry
            db_id: Database ID for precise lookup

        Returns:
            {{ItemLink|PageTitle|image=ImageName.png|text=DisplayText}} with applicable params
            {{ItemLink|PageTitle}} if no overrides needed
        """
        from .core import EntityType

        entity = EntityRef(
            entity_type=EntityType.ITEM,
            db_id=db_id,
            db_name=fallback_name,
            resource_name=resource_name,
        )

        title = self.resolve_item_title(resource_name, fallback_name, db_id)
        display_name = self.registry.get_display_name(entity)
        image_name = self.registry.get_image_name(entity)

        params = []
        if image_name != title:
            params.append(f"image={image_name}.png")
        if display_name != title:
            params.append(f"text={display_name}")

        if params:
            return f"{{{{ItemLink|{title}|{'|'.join(params)}}}}}"
        return f"{{{{ItemLink|{title}}}}}"

    def ability_link(self, resource_name: str, fallback_name: str) -> str:
        """Generate {{AbilityLink|...}} for an ability (spell/skill).

        Tries SPELL first, then SKILL. Both map to unified {{AbilityLink}} template.

        Args:
            resource_name: Ability resource name for lookup
            fallback_name: Display name if not in registry

        Returns:
            {{AbilityLink|PageTitle|image=ImageName.png|text=DisplayText}} with applicable params
            {{AbilityLink|PageTitle}} if no overrides needed
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
            display_name = self.registry.get_display_name(spell_entity)
            image_name = self.registry.get_image_name(spell_entity)

            params = []
            if image_name != title:
                params.append(f"image={image_name}.png")
            if display_name != title:
                params.append(f"text={display_name}")

            if params:
                return f"{{{{AbilityLink|{title}|{'|'.join(params)}}}}}"
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
            display_name = self.registry.get_display_name(skill_entity)
            image_name = self.registry.get_image_name(skill_entity)

            params = []
            if image_name != title:
                params.append(f"image={image_name}.png")
            if display_name != title:
                params.append(f"text={display_name}")

            if params:
                return f"{{{{AbilityLink|{title}|{'|'.join(params)}}}}}"
            return f"{{{{AbilityLink|{title}}}}}"

        # Fallback
        return f"{{{{AbilityLink|{fallback_name}}}}}"

    def character_link(self, entity_ref: EntityRef) -> str:
        """Generate standard MediaWiki link for a character.

        Uses [[Page]] or [[Page|Display]] syntax, consistent with zones and factions.

        Args:
            entity_ref: Character EntityRef

        Returns:
            [[PageTitle|DisplayText]] if display differs
            [[PageTitle]] otherwise
        """
        page = self.registry.resolve_entity(entity_ref)
        title = page.title if page else entity_ref.db_name

        display_name = self.registry.get_display_name(entity_ref)

        if display_name != title:
            return f"[[{title}|{display_name}]]"
        return f"[[{title}]]"
