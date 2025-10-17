# Repository Query Design Questions

**Status**: Draft
**Date**: 2025-10-17
**Context**: Phase 3 Task 2.1 - Adding repository query methods for wiki generation

---

## Questions to Answer

### 1. Query Return Types

**Question**: Should repository queries return nested entities or flat data structures?

**Options**:
- **A) Nested entities**: `Item` with embedded `ItemStats[]`, `Character` with embedded `Spell[]`
- **B) Flat data**: Return tuples/dicts with joined data, let caller assemble
- **C) Separate queries**: `get_item()` + `get_item_stats()` + `get_item_classes()` etc.

**Analysis**:
- Template needs: Items need stats (3 qualities), classes (list), effects (spell names)
- Old code: Used flat queries with JOINs, enriched after
- Phase 2 entities: Designed to hold all data (see Item entity fields)

**Recommendation**: **Option A (Nested entities)** - Return fully populated domain entities
- Matches Phase 2 entity design
- Simplifies caller code
- Clear ownership of data transformation

**Decision**: Nested entities with proper relationship loading

---

### 2. Junction Table Handling

**Question**: How should we handle many-to-many relationships (junction tables)?

**Examples**:
- `ItemClasses` - Item → Classes mapping
- `ItemStats` - Item → Quality → Stats mapping
- `CharacterAttackSpells` - Character → Spells mapping
- `SpellClasses` - Spell → Classes mapping

**Options**:
- **A) Load in query**: JOIN and aggregate in SQL (GROUP_CONCAT, etc.)
- **B) Separate enrichment**: Query main entity, then enrich with junction data
- **C) Lazy loading**: Query on demand when accessed

**Analysis**:
- Old code: Used `JunctionEnricher` for post-query enrichment
- SQL complexity: GROUP_CONCAT works but is database-specific
- Performance: Separate queries more flexible but potentially slower

**Recommendation**: **Option B (Separate enrichment)** - Keep old pattern
- Already proven to work
- Easier to maintain
- Database-agnostic

**Decision**: Use enrichment pattern - query main entity, then enrich relationships

---

### 3. Query Naming Convention

**Question**: What naming pattern for query methods?

**Options**:
- **A) Generic**: `get_all()`, `get_by_id()`, `find()`
- **B) Use case specific**: `get_items_for_wiki()`, `get_vendor_items()`
- **C) Query descriptor**: `get_items_with_stats_and_classes()`

**Analysis**:
- Plan requirement: "specialized queries for specific use cases"
- YAGNI principle: Add only what's needed
- Documentation: Name should indicate purpose

**Recommendation**: **Option B (Use case specific)** - Clear purpose in name
- `get_items_for_wiki_generation()` - Clear this is for wiki
- `get_character_with_abilities(character_id)` - Clear what's included
- `get_craftable_items()` - Clear filter criteria

**Decision**: Use case specific names with docstrings explaining usage

---

### 4. Filtering Strategy

**Question**: Should queries have built-in filters or return everything?

**Examples**:
- Filter by obtainability (exclude debug items?)
- Filter by visibility (exclude hidden spells?)
- Filter by completeness (exclude items with missing names?)

**Options**:
- **A) Filter in query**: Only return "valid" entities
- **B) Return everything**: Let caller filter
- **C) Configurable**: Add optional filter parameters

**Analysis**:
- Old code: Filtered obtainability in `get_items()` with `obtainable_only` param
- Wiki needs: Probably wants all items (even if unobtainable, show as "unobtainable")
- Data quality: Some items have blank names (should exclude these)

**Recommendation**: **Option A (Filter in query)** - Sensible defaults
- Always filter blank names (data quality issue)
- Don't filter obtainability (wiki decides what to show)
- Document filter behavior clearly

**Decision**: Filter data quality issues, not game mechanics

---

### 5. Performance Considerations

**Question**: How to handle large result sets?

**Analysis**:
- Database size: ~800 items, ~200 spells, ~500 characters
- Memory: All entities fit in memory easily (< 10 MB)
- Pagination: Not needed for these sizes

**Recommendation**: Return full result sets - no pagination needed

**Decision**: No pagination, return all results

---

### 6. Caching Strategy

**Question**: Should repository queries cache results?

**Analysis**:
- Usage pattern: Wiki generation runs once, queries all entities
- Data changes: Only on game update (rare)
- Memory: Caching all entities is fine (< 10 MB)

**Recommendation**: No caching in repository - let caller cache if needed

**Decision**: No caching - keep repositories simple

---

## Required Queries by Entity Type

### Items

**For wiki generation** (all item types):
```python
def get_items_for_wiki_generation(self) -> list[Item]:
    """Get all items for wiki page generation.

    Returns items with:
    - Basic fields (name, resource_name, lore, etc.)
    - Quality stats (via ItemStats table)
    - Class restrictions (via ItemClasses junction)
    - Crafting recipes (via CraftingRecipes/CraftingRewards junction)

    Used by: Item page generators (weapons, armor, consumables, etc.)
    """
```

**For specific item lookups**:
```python
def get_item_by_resource_name(self, resource_name: str) -> Item | None:
    """Get single item by resource name.

    Used by: Individual page updates, cross-references
    """
```

**For vendor tables**:
```python
def get_vendor_items(self, character_resource_name: str) -> list[Item]:
    """Get items sold by specific vendor.

    Used by: Vendor NPC pages
    """
```

**For crafting information**:
```python
def get_craftable_items(self) -> list[Item]:
    """Get items that can be crafted (have recipes).

    Used by: Crafting guide pages
    """
```

### Characters

**For wiki generation**:
```python
def get_characters_for_wiki_generation(self) -> list[Character]:
    """Get all characters (NPCs/enemies) for wiki generation.

    Returns characters with:
    - Basic fields (name, level, faction, etc.)
    - Abilities (spells/skills via junction tables)
    - Loot tables (via LootDrops)
    - Spawn points (via SpawnPointCharacters)
    - Dialogs (via CharacterDialogs)

    Used by: Character/Enemy page generators
    """
```

**For specific lookups**:
```python
def get_character_by_resource_name(self, resource_name: str) -> Character | None:
    """Get single character by resource name.

    Used by: Individual page updates, cross-references
    """
```

**For spawn point data**:
```python
def get_characters_at_spawn_point(self, spawn_point_id: str) -> list[Character]:
    """Get characters that spawn at specific location.

    Used by: Zone pages, spawn point documentation
    """
```

### Spells

**For wiki generation**:
```python
def get_spells_for_wiki_generation(self) -> list[Spell]:
    """Get all spells for wiki generation.

    Returns spells with:
    - Basic fields (name, description, effects, etc.)
    - Class restrictions (via SpellClasses junction)
    - Items that grant spell (via Items.ItemEffectOnClick, etc.)

    Used by: Spell/Ability page generators
    """
```

**For specific lookups**:
```python
def get_spell_by_resource_name(self, resource_name: str) -> Spell | None:
    """Get single spell by resource name.

    Used by: Individual page updates, cross-references
    """
```

### Skills

**For wiki generation**:
```python
def get_skills_for_wiki_generation(self) -> list[Skill]:
    """Get all skills for wiki generation.

    Returns skills with:
    - Basic fields (name, description, effects, etc.)
    - Class restrictions (via SkillClasses junction)
    - Items that grant skill (via Items.TeachSkill, etc.)

    Used by: Skill/Ability page generators
    """
```

### Quests (DEFER - Not in Phase 3 scope)

Future implementation - complex relationships

### Factions (DEFER - Not in Phase 3 scope)

Future implementation - medium priority

---

## Design Decisions Summary

1. **Return Type**: Nested entities (fully populated domain objects)
2. **Junction Tables**: Separate enrichment pattern (like old code)
3. **Naming**: Use case specific names (`get_X_for_wiki_generation`)
4. **Filtering**: Filter data quality issues, not game mechanics
5. **Performance**: No pagination needed (small datasets)
6. **Caching**: No caching in repositories

---

## Implementation Plan

### Phase 1: Items (Highest Priority)
- `get_items_for_wiki_generation()` - Core query
- `get_item_by_resource_name()` - Lookups
- Enrich with: ItemStats, ItemClasses, CraftingRecipes, CraftingRewards

### Phase 2: Characters
- `get_characters_for_wiki_generation()` - Core query
- `get_character_by_resource_name()` - Lookups
- Enrich with: Abilities (spells/skills), LootDrops, SpawnPoints

### Phase 3: Spells & Skills
- `get_spells_for_wiki_generation()` - Core query
- `get_skills_for_wiki_generation()` - Core query
- Single lookups as needed
- Enrich with: SpellClasses, items that grant abilities

### Phase 4: Additional Queries (As Needed)
- Add vendor, crafting, spawn point queries only when generators need them
- Follow YAGNI - don't speculate

---

## Open Questions

1. **Should we reuse old JunctionEnricher?**
   - Old code has `JunctionEnricher` class
   - Works well, proven pattern
   - **Answer**: Yes, reuse or adapt for new domain entities

2. **How to handle optional relationships?**
   - Item with no stats (consumables, quest items)
   - Character with no abilities (vendors, quest givers)
   - **Answer**: Return entity with empty lists/None for missing relationships

3. **Should queries log/track performance?**
   - Useful for debugging slow queries
   - **Answer**: Add debug logging, not production metrics (YAGNI)

4. **Error handling for malformed data?**
   - What if JOIN returns unexpected results?
   - What if enrichment fails?
   - **Answer**: Fail loudly (Phase 3 principle), log clearly

---

## Notes

- Start with Items - most complex and highest priority
- Test with 28KB fixture database
- Each query should have integration test
- Document which generator uses each query
- Follow Phase 3 principle: **YAGNI** - only add what's needed now
