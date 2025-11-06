"""Registry resolver for entity name resolution.

This module provides a service for resolving entity names to wiki page titles,
display names, and image names. It queries the registry for manual overrides
and falls back to entity name fields when no override exists.

Resolution strategy:
1. Check registry for override (by stable_key)
2. If override exists, use it
3. If no override, fall back to entity's name field (ItemName, NPCName, etc.)
4. If entity is marked as excluded, return None

Example usage:
    >>> from erenshor.registry.resolver import RegistryResolver
    >>> from pathlib import Path
    >>>
    >>> resolver = RegistryResolver(Path(".erenshor/registry/registry.db"))
    >>>
    >>> # Resolve with override
    >>> page_title = resolver.resolve_page_title("character:Brackish Crocodile", "Brackish Crocodile")
    >>> print(page_title)  # "A Brackish Croc" (from mapping.json)
    >>>
    >>> # Resolve with fallback
    >>> page_title = resolver.resolve_page_title("item:Iron Sword", "Iron Sword")
    >>> print(page_title)  # "Iron Sword" (no override, uses fallback)
    >>>
    >>> # Excluded entity
    >>> page_title = resolver.resolve_page_title("character:Player", "Player")
    >>> print(page_title)  # None (excluded from wiki)
"""

from pathlib import Path

from loguru import logger
from sqlmodel import Session, create_engine

from .operations import get_entity


class RegistryResolver:
    """Resolves entity names to wiki page titles, display names, and image names.

    This service queries the registry database for manual overrides and falls back
    to entity name fields when no override exists.
    """

    def __init__(self, registry_db_path: Path) -> None:
        """Initialize the resolver with a registry database.

        Args:
            registry_db_path: Path to the registry database file
        """
        self.registry_db_path = registry_db_path
        self.engine = create_engine(f"sqlite:///{registry_db_path}")
        logger.debug(f"RegistryResolver initialized with database: {registry_db_path}")

    def resolve_page_title(self, stable_key: str, entity_name: str) -> str | None:
        """Resolve entity stable key to wiki page title.

        Args:
            stable_key: Stable key in format "entity_type:resource_name"
            entity_name: Entity's display name from game data (ItemName, NPCName, etc.)

        Returns:
            Wiki page title (override or fallback to entity_name), or None if excluded

        Example:
            >>> resolver.resolve_page_title("character:Brackish Crocodile", "Brackish Crocodile")
            "A Brackish Croc"
            >>> resolver.resolve_page_title("item:Iron Sword", "Iron Sword")
            "Iron Sword"
            >>> resolver.resolve_page_title("character:Player", "Player")
            None  # excluded
        """
        with Session(self.engine) as session:
            entity = get_entity(session, stable_key)

            if entity:
                # Entity has registry entry
                if entity.excluded:
                    logger.debug(f"Entity {stable_key} is excluded from wiki")
                    return None

                if entity.page_title:
                    logger.debug(f"Using page_title override for {stable_key}: {entity.page_title!r}")
                    return entity.page_title

            # Fall back to entity name
            logger.debug(f"Using entity name fallback for {stable_key}: {entity_name!r}")
            return entity_name

    def resolve_display_name(self, stable_key: str, entity_name: str) -> str:
        """Resolve entity stable key to display name.

        Args:
            stable_key: Stable key in format "entity_type:resource_name"
            entity_name: Entity's display name from game data (ItemName, NPCName, etc.)

        Returns:
            Display name (override or fallback to entity_name)

        Note:
            Always returns a name, even for excluded entities. Exclusion filtering
            should be done separately via resolve_page_title or explicit checks.

        Example:
            >>> resolver.resolve_display_name("character:Brackish Crocodile", "Brackish Crocodile")
            "Brackish Crocodile"  # or override if exists
        """
        with Session(self.engine) as session:
            entity = get_entity(session, stable_key)

            if entity and entity.display_name:
                logger.debug(f"Using display_name override for {stable_key}: {entity.display_name!r}")
                return entity.display_name

            # Fall back to entity name
            logger.debug(f"Using entity name fallback for {stable_key}: {entity_name!r}")
            return entity_name

    def resolve_image_name(self, stable_key: str, entity_name: str) -> str | None:
        """Resolve entity stable key to image filename.

        Args:
            stable_key: Stable key in format "entity_type:resource_name"
            entity_name: Entity's display name from game data (ItemName, NPCName, etc.)

        Returns:
            Image filename (override or fallback to entity_name), or None if excluded

        Example:
            >>> resolver.resolve_image_name("item:Sword of Power", "Sword of Power")
            "SwordOfPower.png"  # or override if exists
        """
        with Session(self.engine) as session:
            entity = get_entity(session, stable_key)

            if entity:
                # Entity has registry entry
                if entity.excluded:
                    logger.debug(f"Entity {stable_key} is excluded from wiki")
                    return None

                if entity.image_name:
                    logger.debug(f"Using image_name override for {stable_key}: {entity.image_name!r}")
                    return entity.image_name

            # Fall back to entity name
            logger.debug(f"Using entity name fallback for {stable_key}: {entity_name!r}")
            return entity_name

    def is_excluded(self, stable_key: str) -> bool:
        """Check if entity is excluded from wiki.

        Args:
            stable_key: Stable key in format "entity_type:resource_name"

        Returns:
            True if entity should be excluded from wiki, False otherwise

        Example:
            >>> resolver.is_excluded("character:Player")
            True
            >>> resolver.is_excluded("item:Iron Sword")
            False
        """
        with Session(self.engine) as session:
            entity = get_entity(session, stable_key)
            return entity.excluded if entity else False

    def item_link(self, resource_name: str, item_name: str) -> str:
        """Generate {{ItemLink|...}} template for an item.

        Args:
            resource_name: Item resource name (internal identifier)
            item_name: Item display name (ItemName)

        Returns:
            {{ItemLink|PageTitle|image=ImageName.png|text=DisplayText}} with applicable params
            {{ItemLink|PageTitle}} if no overrides needed
            Plain display name (no link) if excluded

        Example:
            >>> resolver.item_link("IronSword", "Iron Sword")
            "{{ItemLink|Iron Sword}}"
        """
        from .resource_names import build_stable_key
        from .schema import EntityType

        stable_key = build_stable_key(EntityType.ITEM, resource_name)
        page_title = self.resolve_page_title(stable_key, item_name)

        if page_title is None:
            logger.debug(f"Item {resource_name} is excluded, returning plain display name")
            return item_name

        # Get display name and image overrides
        display_name = self.resolve_display_name(stable_key, item_name)
        image_name = self.resolve_image_name(stable_key, item_name)

        # Build template parameters
        params = []
        if image_name and image_name != page_title:
            # Add .png extension if not already present
            img = image_name if image_name.endswith(".png") else f"{image_name}.png"
            params.append(f"image={img}")
        if display_name and display_name != page_title:
            params.append(f"text={display_name}")

        if params:
            return f"{{{{ItemLink|{page_title}|{'|'.join(params)}}}}}"
        return f"{{{{ItemLink|{page_title}}}}}"

    def faction_link(self, faction_refname: str, faction_display_name: str) -> str:
        """Generate standard MediaWiki link for a faction.

        Uses [[Page]] or [[Page|Display]] syntax.

        Args:
            faction_refname: Faction REFNAME (internal identifier)
            faction_display_name: Faction display name (FactionDesc)

        Returns:
            [[PageTitle|DisplayText]] if display differs
            [[PageTitle]] otherwise
            Plain display name (no link) if excluded

        Example:
            >>> resolver.faction_link("AzureCitizens", "The Citizens of Port Azure")
            "[[The Citizens of Port Azure]]"
        """
        from .resource_names import build_stable_key
        from .schema import EntityType

        stable_key = build_stable_key(EntityType.FACTION, faction_refname)
        page_title = self.resolve_page_title(stable_key, faction_display_name)

        if page_title is None:
            logger.debug(f"Faction {faction_refname} is excluded, returning plain display name")
            return faction_display_name

        display_name = self.resolve_display_name(stable_key, faction_display_name)

        if display_name and display_name != page_title:
            return f"[[{page_title}|{display_name}]]"
        return f"[[{page_title}]]"

    def zone_link(self, scene_name: str, zone_display_name: str) -> str:
        """Generate standard MediaWiki link for a zone.

        Uses [[Page]] or [[Page|Display]] syntax.

        Args:
            scene_name: Scene name (internal identifier)
            zone_display_name: Zone display name (ZoneName from ZoneAnnounces)

        Returns:
            [[PageTitle|DisplayText]] if display differs
            [[PageTitle]] otherwise
            Plain display name (no link) if excluded

        Example:
            >>> resolver.zone_link("Azure", "Port Azure")
            "[[Port Azure]]"
        """
        from .resource_names import build_stable_key
        from .schema import EntityType

        stable_key = build_stable_key(EntityType.ZONE, scene_name)
        page_title = self.resolve_page_title(stable_key, zone_display_name)

        if page_title is None:
            logger.debug(f"Zone {scene_name} is excluded, returning plain display name")
            return zone_display_name

        display_name = self.resolve_display_name(stable_key, zone_display_name)

        if display_name and display_name != page_title:
            return f"[[{page_title}|{display_name}]]"
        return f"[[{page_title}]]"
