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
    entity_type: EntityType,
    resource_name: str,
    page_title: str | None = None,
    display_name: str | None = None,
    image_name: str | None = None,
    excluded: bool = False,
) -> EntityRecord:
    """Register or update an entity override in the registry.

    Uses upsert pattern: if an entity with the same entity_type and resource_name
    already exists, it updates the override fields. Otherwise, creates a new entity record.

    Only entities with custom overrides should be registered. The registry stores
    ONLY overrides - if all fields are None and excluded is False, the entity should
    not be registered.

    Args:
        session: SQLModel database session
        entity_type: Type of entity (item, spell, character, etc.)
        resource_name: Stable resource identifier from game data
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
        ...         EntityType.ITEM,
        ...         "iron_sword",
        ...         page_title="Iron Sword (Weapon)",
        ...     )
        ...     print(f"Registered override: {entity.page_title}")
        Registered override: Iron Sword (Weapon)
    """
    # Check if entity already exists
    statement = select(EntityRecord).where(
        EntityRecord.entity_type == entity_type,
        EntityRecord.resource_name == resource_name,
    )
    existing = session.exec(statement).first()

    if existing:
        # Update existing entity
        existing.page_title = page_title
        existing.display_name = display_name
        existing.image_name = image_name
        existing.excluded = excluded

        session.add(existing)
        session.commit()
        session.refresh(existing)

        logger.debug(
            f"Updated entity: {entity_type.value}:{resource_name} "
            f"(id={existing.id}, page_title={page_title!r}, excluded={excluded})"
        )

        return existing

    # Create new entity
    entity = EntityRecord(
        entity_type=entity_type,
        resource_name=resource_name,
        page_title=page_title,
        display_name=display_name,
        image_name=image_name,
        excluded=excluded,
    )

    session.add(entity)
    session.commit()
    session.refresh(entity)

    logger.info(
        f"Registered new entity: {entity_type.value}:{resource_name} "
        f"(id={entity.id}, page_title={page_title!r}, excluded={excluded})"
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
        select(EntityRecord).order_by(
            EntityRecord.entity_type,
            EntityRecord.display_name,  # type: ignore[arg-type]
        )
    ).all()

    # Group by (entity_type, display_name)
    groups: dict[tuple[EntityType, str], list[EntityRecord]] = {}
    for entity in all_entities:
        if entity.display_name is None:
            raise ValueError(f"Entity {entity.entity_type}:{entity.resource_name} (id={entity.id}) has no display_name")
        key = (entity.entity_type, entity.display_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(entity)

    # Find groups with multiple entities (conflicts)
    for (entity_type, display_name), entities in groups.items():
        if len(entities) > 1:
            conflicts.append((display_name, entities))
            logger.debug(f"Found conflict: {display_name} ({entity_type.value}) has {len(entities)} entities")

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

    logger.info(f"Created conflict record: id={conflict.id}, type={conflict_type}, entity_ids={entity_ids}")

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
            f"Entity {chosen_entity_id} is not part of conflict {conflict_id}. Valid entity IDs: {entity_ids}"
        )

    # Update conflict record
    conflict.resolved = True
    conflict.resolution_entity_id = chosen_entity_id
    conflict.resolution_notes = notes
    conflict.resolved_at = datetime.now(UTC)

    session.add(conflict)
    session.commit()

    logger.info(f"Resolved conflict: id={conflict_id}, chosen_entity={chosen_entity_id}, notes={notes!r}")


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
        # Parse stable key
        try:
            entity_type, resource_name = parse_stable_key(stable_key)
        except ValueError as e:
            logger.warning(f"Skipping invalid stable key '{stable_key}': {e}")
            continue

        # Check if entity is excluded (wiki_page_name explicitly null in mapping)
        # Note: We check if the key exists but value is null
        excluded = "wiki_page_name" in rule_data and rule_data["wiki_page_name"] is None

        # Extract override fields
        page_title = rule_data.get("wiki_page_name")
        display_name = rule_data.get("display_name")
        image_name = rule_data.get("image_name")

        # Skip if no overrides and not excluded (entity not in mapping.json at all)
        if not excluded and page_title is None and display_name is None and image_name is None:
            logger.debug(f"Skipping {stable_key} - no overrides and not excluded")
            continue

        # Register entity override (including exclusions)
        register_entity(
            session,
            entity_type=entity_type,
            resource_name=resource_name,
            page_title=page_title,
            display_name=display_name,
            image_name=image_name,
            excluded=excluded,
        )
        count += 1

    logger.info(f"Imported {count} entity overrides from {mapping_path}")
    return count
