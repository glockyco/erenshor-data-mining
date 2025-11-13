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

    def __init__(
        self,
        registry_db_path: Path,
        game_db_path: Path,
        mapping_json_path: Path,
    ) -> None:
        """Initialize the resolver with a registry database.

        If the registry database doesn't exist or is empty, it will be automatically
        initialized and populated from the game database, then mapping.json overrides applied.

        If game database or mapping.json is newer than registry.db, the registry will be rebuilt.

        Args:
            registry_db_path: Path to the registry database file
            game_db_path: Path to the game database
            mapping_json_path: Path to mapping.json
        """
        self.registry_db_path = registry_db_path

        if not game_db_path.exists():
            raise FileNotFoundError(f"Cannot initialize registry: game database not found at {game_db_path}")

        if not mapping_json_path.exists():
            raise FileNotFoundError(f"Cannot initialize registry: mapping.json not found at {mapping_json_path}")

        # Check if registry needs initialization or rebuild
        needs_init = False
        if not registry_db_path.exists():
            logger.info(f"Registry database not found at {registry_db_path}, will initialize")
            needs_init = True
        elif registry_db_path.stat().st_size == 0:
            logger.info(f"Registry database is empty at {registry_db_path}, will initialize")
            needs_init = True
        elif game_db_path.stat().st_mtime > registry_db_path.stat().st_mtime:
            logger.info("Game database is newer than registry.db, will rebuild")
            needs_init = True
        elif mapping_json_path.stat().st_mtime > registry_db_path.stat().st_mtime:
            logger.info("mapping.json is newer than registry.db, will rebuild")
            needs_init = True

        if needs_init:
            self._build_registry(registry_db_path, game_db_path, mapping_json_path)

        self.engine = create_engine(f"sqlite:///{registry_db_path}")
        logger.debug(f"RegistryResolver initialized with database: {registry_db_path}")

    def _build_registry(self, db_path: Path, game_db_path: Path, mapping_path: Path) -> None:
        """Build registry database from game database and mapping.json.

        Args:
            db_path: Path to create registry database
            game_db_path: Path to game database
            mapping_path: Path to mapping.json
        """
        from .operations import initialize_registry, load_mapping_json, populate_all_entities

        logger.info(f"Building registry database from {game_db_path} and {mapping_path}")

        # Delete old database if it exists
        if db_path.exists():
            logger.debug(f"Removing existing registry database: {db_path}")
            db_path.unlink()

        # Initialize empty database
        initialize_registry(db_path)

        temp_engine = create_engine(f"sqlite:///{db_path}")
        with Session(temp_engine) as session:
            # First populate all entities from game database
            entity_count = populate_all_entities(session, game_db_path)
            logger.info(f"Populated {entity_count} entities from game database")

            # Then apply overrides from mapping.json
            override_count = load_mapping_json(session, mapping_path)
            logger.info(f"Applied {override_count} overrides from mapping.json")

            session.commit()

        logger.info(f"Registry built successfully: {entity_count} entities with {override_count} overrides")

    def resolve_page_title(self, stable_key: str) -> str | None:
        """Resolve entity stable key to wiki page title.

        Args:
            stable_key: Stable key in format "entity_type:resource_name"

        Returns:
            Wiki page title from registry, or None if excluded

        Example:
            >>> resolver.resolve_page_title("character:brackish crocodile")
            "A Brackish Croc"
            >>> resolver.resolve_page_title("item:iron sword")
            "Iron Sword"
            >>> resolver.resolve_page_title("character:player")
            None
        """
        with Session(self.engine) as session:
            entity = get_entity(session, stable_key)

            if not entity:
                raise ValueError(f"Entity not found in registry: {stable_key}")

            if entity.excluded:
                logger.debug(f"Entity {stable_key} is excluded from wiki")
                return None

            if not entity.page_title:
                raise ValueError(f"Entity {stable_key} has no page_title in registry")

            logger.debug(f"Resolved page_title for {stable_key}: {entity.page_title!r}")
            return entity.page_title

    def resolve_display_name(self, stable_key: str) -> str:
        """Resolve entity stable key to display name.

        Args:
            stable_key: Stable key in format "entity_type:resource_name"

        Returns:
            Display name from registry

        Example:
            >>> resolver.resolve_display_name("character:brackish crocodile")
            "Brackish Crocodile"
        """
        with Session(self.engine) as session:
            entity = get_entity(session, stable_key)

            if not entity:
                raise ValueError(f"Entity not found in registry: {stable_key}")

            if not entity.display_name:
                raise ValueError(f"Entity {stable_key} has no display_name in registry")

            logger.debug(f"Resolved display_name for {stable_key}: {entity.display_name!r}")
            return entity.display_name

    def resolve_image_name(self, stable_key: str) -> str | None:
        """Resolve entity stable key to image filename.

        Args:
            stable_key: Stable key in format "entity_type:resource_name"

        Returns:
            Image filename from registry, or None if excluded

        Example:
            >>> resolver.resolve_image_name("item:sword of power")
            "Sword of Power"
        """
        with Session(self.engine) as session:
            entity = get_entity(session, stable_key)

            if not entity:
                raise ValueError(f"Entity not found in registry: {stable_key}")

            if entity.excluded:
                logger.debug(f"Entity {stable_key} is excluded from wiki")
                return None

            if not entity.image_name:
                raise ValueError(f"Entity {stable_key} has no image_name in registry")

            logger.debug(f"Resolved image_name for {stable_key}: {entity.image_name!r}")
            return entity.image_name

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

    def get_stable_keys_for_page(self, page_title: str) -> list[str]:
        """Get all stable keys for entities that map to a given page title.

        This is a reverse lookup from page title to stable keys. Useful for
        finding which entities contribute to a multi-entity page.

        Args:
            page_title: Wiki page title

        Returns:
            List of stable keys for all entities on this page

        Example:
            >>> resolver.get_stable_keys_for_page("Aura: Blessing of Stone")
            ["spell:aura - blessing of stone", "skill:aura - blessing of stone"]
        """
        from sqlmodel import select

        from .schema import EntityRecord

        with Session(self.engine) as session:
            statement = select(EntityRecord).where(EntityRecord.page_title == page_title)
            entities = session.exec(statement).all()

            if not entities:
                logger.warning(f"No entities found for page title: {page_title}")
                return []

            stable_keys = [entity.stable_key for entity in entities]
            logger.debug(f"Found {len(stable_keys)} entities for page {page_title!r}: {stable_keys}")
            return stable_keys

    def item_link(self, stable_key: str) -> str:
        """Generate {{ItemLink|...}} template for an item.

        Args:
            stable_key: Item stable key string (e.g., "item:iron sword")

        Returns:
            {{ItemLink|PageTitle|image=ImageName.png|text=DisplayText}} with applicable params
            {{ItemLink|PageTitle}} if no overrides needed
            Plain display name (no link) if excluded

        Example:
            >>> item = Item(stable_key="item:iron sword", ...)
            >>> resolver.item_link(item.stable_key)
            "{{ItemLink|Iron Sword}}"
        """
        page_title = self.resolve_page_title(stable_key)

        if page_title is None:
            display_name = self.resolve_display_name(stable_key)
            logger.debug(f"Entity {stable_key} is excluded")
            return display_name

        display_name = self.resolve_display_name(stable_key)
        image_name = self.resolve_image_name(stable_key)

        params = []
        if image_name and image_name != page_title:
            img = image_name if image_name.endswith(".png") else f"{image_name}.png"
            params.append(f"image={img}")
        if display_name and display_name != page_title:
            params.append(f"text={display_name}")

        if params:
            return f"{{{{ItemLink|{page_title}|{'|'.join(params)}}}}}"
        return f"{{{{ItemLink|{page_title}}}}}"

    def ability_link(self, stable_key: str) -> str:
        """Generate {{AbilityLink|...}} template for a spell or skill.

        Args:
            stable_key: Spell/skill stable key from Spell.stable_key or Skill.stable_key property

        Returns:
            {{AbilityLink|PageTitle|image=ImageName.png|text=DisplayText}} with applicable params
            {{AbilityLink|PageTitle}} if no overrides needed
            Plain display name (no link) if excluded

        Example:
            >>> spell = Spell(resource_name="gen - stun", ...)
            >>> resolver.ability_link(spell.stable_key)
            "{{AbilityLink|Stun}}"
        """
        page_title = self.resolve_page_title(stable_key)

        if page_title is None:
            display_name = self.resolve_display_name(stable_key)
            logger.debug(f"Entity {stable_key} is excluded")
            return display_name

        display_name = self.resolve_display_name(stable_key)
        image_name = self.resolve_image_name(stable_key)

        params = []
        if image_name and image_name != page_title:
            img = image_name if image_name.endswith(".png") else f"{image_name}.png"
            params.append(f"image={img}")
        if display_name and display_name != page_title:
            params.append(f"text={display_name}")

        if params:
            return f"{{{{AbilityLink|{page_title}|{'|'.join(params)}}}}}"
        return f"{{{{AbilityLink|{page_title}}}}}"

    def faction_link(self, stable_key: str) -> str:
        """Generate standard MediaWiki link for a faction.

        Uses [[Page]] or [[Page|Display]] syntax.

        Args:
            stable_key: Faction stable key from Faction.stable_key property

        Returns:
            [[PageTitle|DisplayText]] if display differs
            [[PageTitle]] otherwise
            Plain display name (no link) if excluded

        Example:
            >>> faction = Faction(refname="AzureCitizens", ...)
            >>> resolver.faction_link(faction.stable_key)
            "[[The Citizens of Port Azure]]"
        """
        page_title = self.resolve_page_title(stable_key)

        if page_title is None:
            display_name = self.resolve_display_name(stable_key)
            logger.debug(f"Entity {stable_key} is excluded")
            return display_name

        display_name = self.resolve_display_name(stable_key)

        if display_name and display_name != page_title:
            return f"[[{page_title}|{display_name}]]"
        return f"[[{page_title}]]"

    def zone_link(self, stable_key: str) -> str:
        """Generate standard MediaWiki link for a zone.

        Uses [[Page]] or [[Page|Display]] syntax.

        Args:
            stable_key: Zone stable key from Zone.stable_key property

        Returns:
            [[PageTitle|DisplayText]] if display differs
            [[PageTitle]] otherwise
            Plain display name (no link) if excluded

        Example:
            >>> zone = Zone(scene="Azure", ...)
            >>> resolver.zone_link(zone.stable_key)
            "[[Port Azure]]"
        """
        page_title = self.resolve_page_title(stable_key)

        if page_title is None:
            display_name = self.resolve_display_name(stable_key)
            logger.debug(f"Entity {stable_key} is excluded")
            return display_name

        display_name = self.resolve_display_name(stable_key)

        if display_name and display_name != page_title:
            return f"[[{page_title}|{display_name}]]"
        return f"[[{page_title}]]"

    def quest_link(self, stable_key: str) -> str:
        """Generate {{QuestLink|...}} template for a quest.

        Args:
            stable_key: Quest stable key from Quest.stable_key property

        Returns:
            {{QuestLink|link=PageTitle{{!}}DisplayText}} if display differs
            {{QuestLink|PageTitle}} if no overrides needed
            Plain display name (no link) if excluded

        Example:
            >>> quest = Quest(db_name="CatForDeer", ...)
            >>> resolver.quest_link(quest.stable_key)
            "{{QuestLink|A Cat for a Deer}}"
        """
        page_title = self.resolve_page_title(stable_key)

        if page_title is None:
            display_name = self.resolve_display_name(stable_key)
            logger.debug(f"Entity {stable_key} is excluded")
            return display_name

        display_name = self.resolve_display_name(stable_key)

        if display_name and display_name != page_title:
            return f"{{{{QuestLink|link={page_title}{{{{!}}}}{display_name}}}}}"
        return f"{{{{QuestLink|{page_title}}}}}"

    def character_link(self, stable_key: str) -> str:
        """Generate standard MediaWiki link for a character.

        Uses [[Page]] or [[Page|Display]] syntax, consistent with zones and factions.

        Args:
            stable_key: Character stable key from Character.stable_key property

        Returns:
            [[PageTitle|DisplayText]] if display differs
            [[PageTitle]] otherwise
            Plain display name (no link) if excluded

        Example:
            >>> character = Character(object_name="Goblin", ...)
            >>> resolver.character_link(character.stable_key)
            "[[Goblin]]"
        """
        page_title = self.resolve_page_title(stable_key)

        if page_title is None:
            display_name = self.resolve_display_name(stable_key)
            logger.debug(f"Entity {stable_key} is excluded")
            return display_name

        display_name = self.resolve_display_name(stable_key)

        if display_name and display_name != page_title:
            return f"[[{page_title}|{display_name}]]"
        return f"[[{page_title}]]"

    def list_all_keys(self) -> list[str]:
        """List all stable keys in the registry.

        Returns:
            List of all stable keys (including excluded entities)

        Example:
            >>> resolver.list_all_keys()
            ["item:iron sword", "character:goblin", "spell:fireball", ...]
        """
        from sqlmodel import select

        from .schema import EntityRecord

        with Session(self.engine) as session:
            statement = select(EntityRecord.stable_key)
            stable_keys = list(session.exec(statement).all())
            logger.debug(f"Found {len(stable_keys)} entities in registry")
            return stable_keys
