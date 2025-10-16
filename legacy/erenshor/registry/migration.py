"""Migration tools for importing existing mappings and building registry from database."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

from erenshor.registry.core import EntityRef, WikiRegistry

logger = logging.getLogger(__name__)

__all__ = ["MappingImporter", "RegistryBuilder", "MappingRules"]


class MappingRules:
    """Container for all mapping rules (custom, merge, exclude)."""

    def __init__(self) -> None:
        self.custom_mappings: Dict[str, str] = {}  # entity_key -> page_title
        self.excluded_keys: Set[str] = set()  # entity_keys to exclude
        self.display_name_mappings: Dict[str, str] = {}  # entity_key -> display_name
        self.image_name_mappings: Dict[str, str] = {}  # entity_key -> image_name

    def is_excluded(self, entity_key: str) -> bool:
        """Check if an entity should be excluded from registry."""
        return entity_key in self.excluded_keys

    def get_page_title(self, entity_key: str) -> Optional[str]:
        """Get custom page title for an entity, or None if not mapped."""
        return self.custom_mappings.get(entity_key)

    def get_display_name(self, entity_key: str) -> Optional[str]:
        """Get custom display name for an entity, or None if not mapped."""
        return self.display_name_mappings.get(entity_key)

    def get_image_name(self, entity_key: str) -> Optional[str]:
        """Get custom image name for an entity, or None if not mapped."""
        return self.image_name_mappings.get(entity_key)


class MappingImporter:
    """Import existing mapping.json into registry format."""

    def import_manual_mappings(
        self, mapping_file: Path, registry: WikiRegistry
    ) -> MappingRules:
        """Load manual mappings from mapping.json.

        Returns:
            MappingRules containing custom mappings and exclusions
        """
        rules = MappingRules()

        if not mapping_file.exists():
            return rules

        data = json.loads(mapping_file.read_text())

        for key, rule in data.get("rules", {}).items():
            mapping_type = rule.get("mapping_type", "custom")

            if mapping_type == "exclude":
                rules.excluded_keys.add(key)
            elif rule.get("wiki_page_name"):
                page_title = rule["wiki_page_name"]
                rules.custom_mappings[key] = page_title
                registry.set_manual_mapping(key, page_title)

                # Create the page if it doesn't exist (needed for entities like factions
                # that aren't registered through build_from_db but need pages for links)
                registry.get_or_create_page(page_title)

            if rule.get("display_name"):
                display_name = rule["display_name"]
                rules.display_name_mappings[key] = display_name

            if rule.get("image_name"):
                image_name = rule["image_name"]
                rules.image_name_mappings[key] = image_name

        return rules


class RegistryBuilder:
    """Build registry from database."""

    def build_from_db(
        self,
        engine: Any,  # SQLAlchemy Engine
        registry: WikiRegistry,
        mapping_rules: Optional[MappingRules] = None,
    ) -> None:
        """Populate registry with all database entities.

        Args:
            engine: SQLAlchemy database engine
            registry: WikiRegistry to populate
            mapping_rules: Optional MappingRules with custom mappings and exclusions
        """
        from erenshor.infrastructure.database.repositories import (
            get_characters,
            get_items,
            get_skills,
            get_spells,
        )

        from .core import EntityRef

        registry.clear_entity_mappings()

        excluded_count = 0

        for item in get_items(engine, obtainable_only=False):
            entity = EntityRef.from_item(item)
            if mapping_rules and mapping_rules.is_excluded(entity.stable_key):
                excluded_count += 1
                continue
            page_title = self._resolve_page_title(entity, mapping_rules)
            if not page_title:
                page_title = item.ItemName
            registry.register_entity(entity, page_title)
            if mapping_rules:
                display_name = mapping_rules.get_display_name(entity.stable_key)
                if display_name:
                    registry.set_display_name_override(entity.stable_key, display_name)
                image_name = mapping_rules.get_image_name(entity.stable_key)
                if image_name:
                    registry.set_image_name_override(entity.stable_key, image_name)

        for char in get_characters(engine):
            entity = EntityRef.from_character(char)
            if mapping_rules and mapping_rules.is_excluded(entity.stable_key):
                excluded_count += 1
                continue
            page_title = self._resolve_page_title(entity, mapping_rules)
            if not page_title:
                page_title = char.NPCName
            registry.register_entity(entity, page_title)
            if mapping_rules:
                display_name = mapping_rules.get_display_name(entity.stable_key)
                if display_name:
                    registry.set_display_name_override(entity.stable_key, display_name)
                image_name = mapping_rules.get_image_name(entity.stable_key)
                if image_name:
                    registry.set_image_name_override(entity.stable_key, image_name)

        for spell in get_spells(engine, obtainable_only=False):
            entity = EntityRef.from_spell(spell)
            if mapping_rules and mapping_rules.is_excluded(entity.stable_key):
                excluded_count += 1
                continue
            page_title = self._resolve_page_title(entity, mapping_rules)
            if not page_title:
                page_title = spell.SpellName
            registry.register_entity(entity, page_title)
            if mapping_rules:
                display_name = mapping_rules.get_display_name(entity.stable_key)
                if display_name:
                    registry.set_display_name_override(entity.stable_key, display_name)
                image_name = mapping_rules.get_image_name(entity.stable_key)
                if image_name:
                    registry.set_image_name_override(entity.stable_key, image_name)

        for skill in get_skills(engine):
            entity = EntityRef.from_skill(skill)
            if mapping_rules and mapping_rules.is_excluded(entity.stable_key):
                excluded_count += 1
                continue
            page_title = self._resolve_page_title(entity, mapping_rules)
            if not page_title:
                page_title = skill.SkillName
            registry.register_entity(entity, page_title)
            if mapping_rules:
                display_name = mapping_rules.get_display_name(entity.stable_key)
                if display_name:
                    registry.set_display_name_override(entity.stable_key, display_name)
                image_name = mapping_rules.get_image_name(entity.stable_key)
                if image_name:
                    registry.set_image_name_override(entity.stable_key, image_name)

        # Remove orphaned pages from entity merges in mapping.json
        orphaned_count = registry.remove_orphaned_pages()
        if orphaned_count > 0:
            logger.info(f"Removed {orphaned_count} orphaned pages from registry")

        if excluded_count > 0:
            logger.info(f"Excluded {excluded_count} entities from registry")

        registry.save()

    def _resolve_page_title(
        self, entity: EntityRef, mapping_rules: Optional[MappingRules]
    ) -> Optional[str]:
        """Resolve page title for an entity."""
        if not mapping_rules:
            return None

        # Check custom mappings
        return mapping_rules.get_page_title(entity.stable_key)
