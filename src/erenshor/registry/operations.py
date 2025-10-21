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

from .resource_names import parse_stable_key
from .schema import ConflictRecord, EntityRecord, EntityType, MigrationRecord


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
    entity_type: EntityType,
    resource_name: str,
    display_name: str,
    wiki_page_title: str | None = None,
    is_manual: bool = False,
) -> EntityRecord:
    """Register or update an entity in the registry.

    Uses upsert pattern: if an entity with the same entity_type and resource_name
    already exists, it updates last_seen and optionally display_name/wiki_page_title.
    Otherwise, creates a new entity record.

    Args:
        session: SQLModel database session
        entity_type: Type of entity (item, spell, character, etc.)
        resource_name: Stable resource identifier from game data
        display_name: Human-readable name shown in game UI
        wiki_page_title: Associated wiki page title (None if no wiki page)
        is_manual: True if wiki page was manually created (not auto-generated)

    Returns:
        EntityRecord instance (newly created or updated)

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     entity = register_entity(
        ...         session,
        ...         EntityType.ITEM,
        ...         "iron_sword",
        ...         "Iron Sword",
        ...         wiki_page_title="Iron Sword",
        ...     )
        ...     print(f"Registered: {entity.display_name}")
        Registered: Iron Sword
    """
    now = datetime.now(UTC)

    # Check if entity already exists
    statement = select(EntityRecord).where(
        EntityRecord.entity_type == entity_type,
        EntityRecord.resource_name == resource_name,
    )
    existing = session.exec(statement).first()

    if existing:
        # Update existing entity
        existing.last_seen = now
        existing.display_name = display_name

        if wiki_page_title is not None:
            existing.wiki_page_title = wiki_page_title

        existing.is_manual = is_manual

        session.add(existing)
        session.commit()
        session.refresh(existing)

        logger.debug(
            f"Updated entity: {entity_type.value}:{resource_name} " f"(id={existing.id}, display_name={display_name!r})"
        )

        return existing

    # Create new entity
    entity = EntityRecord(
        entity_type=entity_type,
        resource_name=resource_name,
        display_name=display_name,
        wiki_page_title=wiki_page_title,
        is_manual=is_manual,
        first_seen=now,
        last_seen=now,
    )

    session.add(entity)
    session.commit()
    session.refresh(entity)

    logger.info(
        f"Registered new entity: {entity_type.value}:{resource_name} "
        f"(id={entity.id}, display_name={display_name!r})"
    )

    return entity


def get_entity(session: Session, stable_key: str) -> EntityRecord | None:
    """Retrieve entity by stable key.

    Parses the stable key into entity_type and resource_name, then queries
    for the matching entity record.

    Args:
        session: SQLModel database session
        stable_key: Stable key in format "entity_type:resource_name"

    Returns:
        EntityRecord if found, None otherwise

    Raises:
        ValueError: If stable_key format is invalid

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
    # Parse stable key
    entity_type, resource_name = parse_stable_key(stable_key)

    # Query for entity
    statement = select(EntityRecord).where(
        EntityRecord.entity_type == entity_type,
        EntityRecord.resource_name == resource_name,
    )
    entity = session.exec(statement).first()

    if entity:
        logger.debug(f"Found entity: {stable_key} (id={entity.id})")
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
        entity_type: If provided, only return entities of this type.
                     If None, return all entities.

    Returns:
        List of EntityRecord instances, ordered by entity_type then resource_name

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
        statement = statement.where(EntityRecord.entity_type == entity_type)

    # Order by entity_type, then resource_name
    statement = statement.order_by(EntityRecord.entity_type, EntityRecord.resource_name)

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
        ...         entity_type = entities[0].entity_type
        ...         print(f"Conflict: {display_name} ({entity_type.value})")
        ...         for entity in entities:
        ...             print(f"  - {entity.resource_name}")
        Conflict: Iron Sword (item)
          - iron_sword_1
          - iron_sword_2
    """
    conflicts: list[tuple[str, list[EntityRecord]]] = []

    # Group entities by entity_type and display_name
    all_entities = session.exec(
        select(EntityRecord).order_by(EntityRecord.entity_type, EntityRecord.display_name)
    ).all()

    # Group by (entity_type, display_name)
    groups: dict[tuple[EntityType, str], list[EntityRecord]] = {}
    for entity in all_entities:
        key = (entity.entity_type, entity.display_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(entity)

    # Find groups with multiple entities (conflicts)
    for (entity_type, display_name), entities in groups.items():
        if len(entities) > 1:
            conflicts.append((display_name, entities))
            logger.debug(f"Found conflict: {display_name} ({entity_type.value}) " f"has {len(entities)} entities")

    logger.info(f"Found {len(conflicts)} name conflicts")
    return conflicts


def create_conflict_record(
    session: Session,
    entity_ids: list[int],
    conflict_type: str,
) -> ConflictRecord:
    """Create a conflict record for tracking.

    Args:
        session: SQLModel database session
        entity_ids: List of entity IDs involved in the conflict
        conflict_type: Type of conflict (e.g., "name_collision", "ambiguous_reference")

    Returns:
        ConflictRecord instance (newly created)

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     conflict = create_conflict_record(
        ...         session,
        ...         entity_ids=[1, 2, 3],
        ...         conflict_type="name_collision",
        ...     )
        ...     print(f"Created conflict record: {conflict.id}")
        Created conflict record: 1
    """
    # Create conflict record
    conflict = ConflictRecord(
        entity_ids=json.dumps(entity_ids),
        conflict_type=conflict_type,
        resolved=False,
        created_at=datetime.now(UTC),
    )

    session.add(conflict)
    session.commit()
    session.refresh(conflict)

    logger.info(f"Created conflict record: id={conflict.id}, " f"type={conflict_type}, entity_ids={entity_ids}")

    return conflict


def resolve_conflict(
    session: Session,
    conflict_id: int,
    chosen_entity_id: int,
    notes: str | None = None,
) -> None:
    """Resolve a conflict by choosing canonical entity.

    Args:
        session: SQLModel database session
        conflict_id: ID of the conflict record to resolve
        chosen_entity_id: ID of the chosen canonical entity
        notes: Optional notes explaining the resolution

    Raises:
        ValueError: If conflict not found or chosen_entity_id not in conflict

    Example:
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     resolve_conflict(
        ...         session,
        ...         conflict_id=1,
        ...         chosen_entity_id=2,
        ...         notes="Chose entity 2 as canonical version",
        ...     )
        ...     print("Conflict resolved")
        Conflict resolved
    """
    # Get conflict record
    conflict = session.get(ConflictRecord, conflict_id)
    if not conflict:
        raise ValueError(f"Conflict not found: {conflict_id}")

    # Verify chosen_entity_id is in conflict
    entity_ids = json.loads(conflict.entity_ids)
    if chosen_entity_id not in entity_ids:
        raise ValueError(
            f"Entity {chosen_entity_id} is not part of conflict {conflict_id}. " f"Valid entity IDs: {entity_ids}"
        )

    # Update conflict record
    conflict.resolved = True
    conflict.resolution_entity_id = chosen_entity_id
    conflict.resolution_notes = notes
    conflict.resolved_at = datetime.now(UTC)

    session.add(conflict)
    session.commit()

    logger.info(f"Resolved conflict: id={conflict_id}, " f"chosen_entity={chosen_entity_id}, notes={notes!r}")


def migrate_from_mapping_json(session: Session, mapping_path: Path) -> int:
    """Import historical entity mappings from mapping.json.

    The mapping.json file contains entity mapping rules in the format:
    {
        "rules": {
            "old_key": {
                "wiki_page_name": "New Page Name",
                ...
            }
        }
    }

    This function extracts old_key -> wiki_page_name mappings and creates
    MigrationRecord entries for historical tracking.

    Args:
        session: SQLModel database session
        mapping_path: Path to mapping.json file

    Returns:
        Number of migration records imported

    Example:
        >>> from pathlib import Path
        >>> from sqlmodel import Session, create_engine
        >>> engine = create_engine("sqlite:///registry.db")
        >>> with Session(engine) as session:
        ...     count = migrate_from_mapping_json(
        ...         session,
        ...         Path("mapping.json"),
        ...     )
        ...     print(f"Imported {count} mappings")
        Imported 275 mappings
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

    # Create migration records
    count = 0
    now = datetime.now(UTC)

    for old_key, rule_data in rules.items():
        # Skip if no wiki_page_name (excluded or invalid)
        wiki_page_name = rule_data.get("wiki_page_name")
        if not wiki_page_name:
            continue

        # Create migration record
        migration = MigrationRecord(
            old_key=old_key,
            new_key=f"{old_key} -> {wiki_page_name}",  # Encode mapping
            migration_date=now,
            notes=f"Imported from mapping.json: {rule_data.get('reason', 'N/A')}",
        )

        session.add(migration)
        count += 1

    # Commit all migrations
    session.commit()

    logger.info(f"Imported {count} migration records from {mapping_path}")
    return count
