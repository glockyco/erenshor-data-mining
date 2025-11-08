"""Core registry operations for entity management.

This module provides CRUD operations, conflict detection, and migration support
for the entity registry system. All operations accept a SQLModel Session parameter
and handle database transactions internally.

Operations:
- initialize_registry: Create database and tables
- register_entity: Register or update an entity (upsert)
- get_entity: Retrieve entity by stable key
- list_entities: List entities with optional type filter
- find_conflicts: Detect name collisions within entity types
- create_conflict_record: Record a conflict for resolution
- resolve_conflict: Mark conflict as resolved with chosen entity
- migrate_from_mapping_json: Import historical mappings

All timestamps use UTC. Session management is the caller's responsibility,
but commit() is called within each function to ensure changes are persisted.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from sqlmodel import Session, SQLModel, create_engine, select

from .schema import ConflictRecord, EntityRecord, EntityType


def initialize_registry(db_path: Path) -> None:
    """Create registry database and tables.

    Creates a new SQLite database at the specified path with all registry tables
    (entities, migrations, conflicts) and indexes. If the database already exists,
    table creation is skipped (existing tables are not modified).

    Args:
        db_path: Path where the database file should be created

    Example:
        >>> from pathlib import Path
        >>> initialize_registry(Path("registry.db"))
        >>> # Database created with all tables and indexes
    """
    logger.info(f"Initializing registry database at {db_path}")

    # Create parent directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create engine and tables
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        SQLModel.metadata.create_all(engine)
    finally:
        engine.dispose()

    logger.info(f"Registry database initialized successfully at {db_path}")


def register_entity(
    session: Session,
    stable_key: str,
    page_title: str | None = None,
    display_name: str | None = None,
    image_name: str | None = None,
    excluded: bool = False,
) -> EntityRecord:
    """Register or update an entity override in the registry.

    Uses upsert pattern: if an entity with the same stable_key already exists,
    it updates the override fields. Otherwise, creates a new entity record.

    Only entities with custom overrides should be registered. The registry stores
    ONLY overrides - if all fields are None and excluded is False, the entity should
    not be registered.

    Args:
        session: SQLModel database session
        stable_key: Stable key from game database (format: "entity_type:resource_name")
        page_title: Custom wiki page title override (None = use entity name)
        display_name: Custom display name override (None = use entity name)
        image_name: Custom image filename override (None = use entity name)
        excluded: True if entity should be excluded from wiki (mapping.json has null wiki_page_name)

    Returns:
        EntityRecord instance (newly created or updated)

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     entity = register_entity(
        ...         session,
        ...         "item:iron_sword",
        ...         page_title="Iron Sword (Weapon)",
        ...     )
        ...     print(f"Registered override: {entity.page_title}")
        Registered override: Iron Sword (Weapon)
    """
    # Check if entity already exists
    statement = select(EntityRecord).where(EntityRecord.stable_key == stable_key)
    existing = session.exec(statement).first()

    if existing:
        # Update existing entity - only override non-None values
        if page_title is not None:
            existing.page_title = page_title
        if display_name is not None:
            existing.display_name = display_name
        if image_name is not None:
            existing.image_name = image_name
        existing.excluded = excluded

        session.add(existing)
        session.commit()
        session.refresh(existing)

        logger.debug(f"Updated entity: {stable_key} (page_title={page_title!r}, excluded={excluded})")

        return existing

    # Extract entity_type from stable_key (format: "entity_type:resource_name")
    entity_type_str = stable_key.split(":", 1)[0]
    entity_type = EntityType(entity_type_str)

    # Create new entity
    entity = EntityRecord(
        stable_key=stable_key,
        entity_type=entity_type,
        page_title=page_title,
        display_name=display_name,
        image_name=image_name,
        excluded=excluded,
    )

    session.add(entity)
    session.commit()
    session.refresh(entity)

    logger.debug(f"Registered new entity: {stable_key} (page_title={page_title!r}, excluded={excluded})")

    return entity


def get_entity(session: Session, stable_key: str) -> EntityRecord | None:
    """Retrieve entity by stable key.

    Args:
        session: SQLModel database session
        stable_key: Stable key in format "entity_type:resource_name"

    Returns:
        EntityRecord if found, None otherwise

    Raises:
        ValueError: If stable_key format is invalid or entity_type is unknown

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     entity = get_entity(session, "item:iron_sword")
        ...     if entity:
        ...         print(f"Found: {entity.display_name}")
        ...     else:
        ...         print("Not found")
        Found: Iron Sword
    """
    # Validate stable key format
    if ":" not in stable_key:
        raise ValueError(f"Invalid stable key format: '{stable_key}' (expected 'entity_type:resource_name')")

    # Validate entity type
    entity_type_str = stable_key.split(":", 1)[0]
    try:
        EntityType(entity_type_str)
    except ValueError as err:
        raise ValueError(f"Unknown entity type: '{entity_type_str}' in stable key '{stable_key}'") from err

    # Query for entity by stable_key
    statement = select(EntityRecord).where(EntityRecord.stable_key == stable_key)
    entity = session.exec(statement).first()

    if entity:
        logger.debug(f"Found entity: {stable_key}")
    else:
        logger.debug(f"Entity not found: {stable_key}")

    return entity


def list_entities(
    session: Session,
    entity_type: EntityType | None = None,
) -> list[EntityRecord]:
    """List entities with optional type filter.

    Args:
        session: SQLModel database session
        entity_type: If provided, only return entities of this type (filters by stable_key prefix).
                     If None, return all entities.

    Returns:
        List of EntityRecord instances, ordered by stable_key

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     # List all items
        ...     items = list_entities(session, EntityType.ITEM)
        ...     print(f"Found {len(items)} items")
        ...
        ...     # List all entities
        ...     all_entities = list_entities(session)
        ...     print(f"Total entities: {len(all_entities)}")
        Found 150 items
        Total entities: 500
    """
    # Build query
    statement = select(EntityRecord)

    if entity_type is not None:
        # Filter by stable_key prefix (e.g., "item:")
        prefix = f"{entity_type.value}:"
        statement = statement.where(EntityRecord.stable_key.like(f"{prefix}%"))  # type: ignore[attr-defined]

    # Order by stable_key
    statement = statement.order_by(EntityRecord.stable_key)

    # Execute query
    entities = list(session.exec(statement).all())

    if entity_type:
        logger.debug(f"Listed {len(entities)} entities of type {entity_type.value}")
    else:
        logger.debug(f"Listed {len(entities)} total entities")

    return entities


def find_conflicts(session: Session) -> list[tuple[str, list[EntityRecord]]]:
    """Detect name conflicts within entity types.

    Finds cases where multiple entities of the same type share the same display_name.
    This indicates potential conflicts requiring resolution.

    Conflicts are detected per-entity-type: two items with the same name is a conflict,
    but an item and spell with the same name is acceptable.

    Args:
        session: SQLModel database session

    Returns:
        List of (display_name, [entity1, entity2, ...]) tuples for each conflict,
        ordered by display_name

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     conflicts = find_conflicts(session)
        ...     for display_name, entities in conflicts:
        ...         # Extract entity_type from stable_key
        ...         entity_type = entities[0].stable_key.split(":")[0]
        ...         print(f"Conflict: {display_name} ({entity_type})")
        ...         for entity in entities:
        ...             print(f"  - {entity.stable_key}")
        Conflict: Iron Sword (item)
          - item:iron_sword_1
          - item:iron_sword_2
    """
    conflicts: list[tuple[str, list[EntityRecord]]] = []

    # Group entities by entity_type and display_name
    all_entities = session.exec(
        select(EntityRecord).order_by(
            EntityRecord.stable_key,
            EntityRecord.display_name,  # type: ignore[arg-type]
        )
    ).all()

    # Group by (entity_type, display_name)
    # Extract entity_type from stable_key
    groups: dict[tuple[str, str], list[EntityRecord]] = {}
    for entity in all_entities:
        if entity.display_name is None:
            raise ValueError(f"Entity {entity.stable_key} has no display_name")
        # Extract entity type from stable_key (format: "entity_type:resource_name")
        entity_type_str = entity.stable_key.split(":", 1)[0] if ":" in entity.stable_key else "unknown"
        key = (entity_type_str, entity.display_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(entity)

    # Find groups with multiple entities (conflicts)
    for (entity_type_str, display_name), entities in groups.items():
        if len(entities) > 1:
            conflicts.append((display_name, entities))
            logger.debug(f"Found conflict: {display_name} ({entity_type_str}) has {len(entities)} entities")

    logger.info(f"Found {len(conflicts)} name conflicts")
    return conflicts


def create_conflict_record(
    session: Session,
    entity_stable_keys: list[str],
    conflict_type: str,
) -> ConflictRecord:
    """Create a conflict record for tracking.

    Args:
        session: SQLModel database session
        entity_stable_keys: List of entity stable keys involved in the conflict
        conflict_type: Type of conflict (e.g., "name_collision", "ambiguous_reference")

    Returns:
        ConflictRecord instance (newly created)

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     conflict = create_conflict_record(
        ...         session,
        ...         entity_stable_keys=["item:sword1", "item:sword2"],
        ...         conflict_type="name_collision",
        ...     )
        ...     print(f"Created conflict record: {conflict.id}")
        Created conflict record: 1
    """
    # Create conflict record
    conflict = ConflictRecord(
        entity_stable_keys=json.dumps(entity_stable_keys),
        conflict_type=conflict_type,
        resolved=False,
        created_at=datetime.now(UTC),
    )

    session.add(conflict)
    session.commit()
    session.refresh(conflict)

    logger.info(
        f"Created conflict record: id={conflict.id}, type={conflict_type}, entity_stable_keys={entity_stable_keys}"
    )

    return conflict


def resolve_conflict(
    session: Session,
    conflict_id: int,
    chosen_stable_key: str,
    notes: str | None = None,
) -> None:
    """Resolve a conflict by choosing canonical entity.

    Args:
        session: SQLModel database session
        conflict_id: ID of the conflict record to resolve
        chosen_stable_key: Stable key of the chosen canonical entity
        notes: Optional notes explaining the resolution

    Raises:
        ValueError: If conflict not found or chosen_stable_key not in conflict

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     resolve_conflict(
        ...         session,
        ...         conflict_id=1,
        ...         chosen_stable_key="item:sword2",
        ...         notes="Chose sword2 as canonical version",
        ...     )
        ...     print("Conflict resolved")
        Conflict resolved
    """
    # Get conflict record
    conflict = session.get(ConflictRecord, conflict_id)
    if not conflict:
        raise ValueError(f"Conflict not found: {conflict_id}")

    # Verify chosen_stable_key is in conflict
    entity_stable_keys = json.loads(conflict.entity_stable_keys)
    if chosen_stable_key not in entity_stable_keys:
        raise ValueError(
            f"Entity {chosen_stable_key} is not part of conflict {conflict_id}. Valid stable keys: {entity_stable_keys}"
        )

    # Update conflict record
    conflict.resolved = True
    conflict.resolution_stable_key = chosen_stable_key
    conflict.resolution_notes = notes
    conflict.resolved_at = datetime.now(UTC)

    session.add(conflict)
    session.commit()

    logger.info(f"Resolved conflict: id={conflict_id}, chosen_entity={chosen_stable_key}, notes={notes!r}")


def populate_all_entities(session: Session, db_path: Path) -> int:
    """Populate registry with ALL entities from game database.

    Scans Items, Spells, Skills, Characters, Quests, Factions (WorldFactions), and Zones tables
    and creates registry entries for every entity with their default names. This should be called
    FIRST to populate the registry, then load_mapping_json() to apply overrides.

    All stable keys are normalized to lowercase for case-insensitive lookups.

    Args:
        session: SQLModel database session
        db_path: Path to game database (erenshor-main.sqlite)

    Returns:
        Number of entities added to registry

    Example:
        >>> from pathlib import Path
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     count = populate_all_entities(session, Path("erenshor-main.sqlite"))
        ...     print(f"Added {count} entities")
        Added 2500 entities
    """
    import sqlite3

    if not db_path.exists():
        logger.error(f"Game database not found: {db_path}")
        return 0

    logger.info(f"Populating registry with all entities from {db_path}")

    # Connect to game database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    count = 0

    # Items
    cursor.execute("SELECT StableKey, ItemName FROM Items")
    for row in cursor.fetchall():
        stable_key = row["StableKey"]
        item_name = row["ItemName"]

        register_entity(
            session,
            stable_key=stable_key,
            page_title=item_name,
            display_name=item_name,
            image_name=item_name,
        )
        count += 1

    # Spells
    cursor.execute("SELECT StableKey, SpellName FROM Spells")
    for row in cursor.fetchall():
        stable_key = row["StableKey"]
        spell_name = row["SpellName"]

        register_entity(
            session,
            stable_key=stable_key,
            page_title=spell_name,
            display_name=spell_name,
            image_name=spell_name,
        )
        count += 1

    # Skills
    cursor.execute("SELECT StableKey, SkillName FROM Skills")
    for row in cursor.fetchall():
        stable_key = row["StableKey"]
        skill_name = row["SkillName"]

        register_entity(
            session,
            stable_key=stable_key,
            page_title=skill_name,
            display_name=skill_name,
            image_name=skill_name,
        )
        count += 1

    # Characters
    cursor.execute("SELECT StableKey, NPCName FROM Characters")
    for row in cursor.fetchall():
        stable_key = row["StableKey"]
        npc_name = row["NPCName"]

        register_entity(
            session,
            stable_key=stable_key,
            page_title=npc_name,
            display_name=npc_name,
            image_name=npc_name,
        )
        count += 1

    # Quests (get name from first QuestVariant)
    cursor.execute("""
        SELECT q.StableKey, qv.QuestName
        FROM Quests q
        JOIN QuestVariants qv ON q.StableKey = qv.QuestStableKey
        GROUP BY q.StableKey
    """)
    for row in cursor.fetchall():
        stable_key = row["StableKey"]
        quest_name = row["QuestName"]

        register_entity(
            session,
            stable_key=stable_key,
            page_title=quest_name,
            display_name=quest_name,
            image_name=quest_name,
        )
        count += 1

    # Factions
    cursor.execute("SELECT StableKey, FactionDesc FROM Factions")
    for row in cursor.fetchall():
        stable_key = row["StableKey"]
        faction_desc = row["FactionDesc"]

        register_entity(
            session,
            stable_key=stable_key,
            page_title=faction_desc,
            display_name=faction_desc,
            image_name=faction_desc,
        )
        count += 1

    # Zones
    cursor.execute("SELECT StableKey, ZoneName FROM Zones")
    for row in cursor.fetchall():
        stable_key = row["StableKey"]
        zone_name = row["ZoneName"]

        register_entity(
            session,
            stable_key=stable_key,
            page_title=zone_name,
            display_name=zone_name,
            image_name=zone_name,
        )
        count += 1

    conn.close()

    logger.info(f"Added {count} entities to registry")
    return count


def load_mapping_json(session: Session, mapping_path: Path) -> int:
    """Import entity overrides from mapping.json into registry.

    The mapping.json file contains entity mapping rules in the format:
    {
        "rules": {
            "entity_type:resource_name": {
                "wiki_page_name": "Custom Page Title",
                "display_name": "Custom Display Name",
                "image_name": "CustomImage.png",
                "mapping_type": "custom"
            }
        }
    }

    This function creates EntityRecord entries for each rule with non-null overrides.
    Only entities with custom mappings are imported - entities without overrides
    are skipped (they will use entity name as default).

    Args:
        session: SQLModel database session
        mapping_path: Path to mapping.json file

    Returns:
        Number of entity overrides imported

    Example:
        >>> from pathlib import Path
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     count = load_mapping_json(
        ...         session,
        ...         Path("mapping.json"),
        ...     )
        ...     print(f"Imported {count} entity overrides")
        Imported 275 entity overrides
    """
    # Check if file exists
    if not mapping_path.exists():
        logger.warning(f"Mapping file not found: {mapping_path}")
        return 0

    # Read JSON file
    try:
        with mapping_path.open() as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read mapping file {mapping_path}: {e}")
        return 0

    # Extract rules
    rules = data.get("rules", {})
    if not rules:
        logger.warning(f"No rules found in mapping file: {mapping_path}")
        return 0

    # Import entity overrides
    count = 0

    for stable_key, rule_data in rules.items():
        # Validate stable key format (should be "entity_type:resource_name")
        if ":" not in stable_key:
            raise ValueError(f"Invalid stable key '{stable_key}': missing ':' separator")

        # Normalize stable key to lowercase for case-insensitive lookups
        normalized_key = stable_key.lower()

        # Check if entity is excluded (wiki_page_name explicitly null in mapping)
        # Note: We check if the key exists but value is null
        excluded = "wiki_page_name" in rule_data and rule_data["wiki_page_name"] is None

        # Extract override fields
        page_title = rule_data.get("wiki_page_name")
        display_name = rule_data.get("display_name")
        image_name = rule_data.get("image_name")

        # Skip if no overrides and not excluded (entity not in mapping.json at all)
        if not excluded and page_title is None and display_name is None and image_name is None:
            logger.debug(f"Skipping {normalized_key} - no overrides and not excluded")
            continue

        # Register entity override (including exclusions)
        register_entity(
            session,
            stable_key=normalized_key,
            page_title=page_title,
            display_name=display_name,
            image_name=image_name,
            excluded=excluded,
        )
        count += 1

    logger.info(f"Imported {count} entity overrides from {mapping_path}")
    return count
