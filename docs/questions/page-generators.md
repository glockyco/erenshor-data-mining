# Page Generator Questions

Questions and design decisions for Phase 3 Task 2.2 - Page Generator Implementation.

## Questions

### 1. Charm Classification Logic

The task description mentions "charms: Specific logic (check old implementation if unclear)".

Looking at the old implementation (`legacy/erenshor/application/generators/items/base.py`), I see:
```python
is_charm = slot_raw.lower() == "charm"
```

**Question**: Is charm classification as simple as `RequiredSlot == "Charm"`? Or is there more complex logic needed?

**Decision**: Based on code review, it appears to be simple slot-based: `RequiredSlot == "Charm"` (case-insensitive).

### 2. Item Stats and Quality Tiers

From the old implementation, weapons and armor generate 3 templates (Normal, Blessed, Godly) based on Quality tiers.

**Question**:
- Where do quality stats come from? Is there a separate ItemStats table?
- How do we query for item stats by quality?
- What if an item has fewer than 3 qualities?

**Investigation needed**: Check if there's a `get_item_stats()` repository method or if we need to create one.

### 3. Proc Effects Extraction

The old code has a `ProcExtractor` class that extracts weapon/armor proc information.

**Question**:
- Is proc extraction in scope for this task?
- Should we create a separate utility class for this?
- What database tables/fields contain proc information?

**Impact**: This affects weapon and armor template context building.

### 4. Source Enrichment (Vendors, Drops, Quests, Crafting)

The old implementation has complex logic for enriching items with:
- Vendor sources
- Drop sources
- Quest sources
- Crafting sources

**Question**: Is source enrichment in scope for Task 2.2, or is it deferred to a later task?

**From task description**: "No field preservation yet - That's Task 2.3, just generate fresh content"

**Interpretation**: We should generate templates with source data IF available from repository queries, but we're not responsible for merging with existing wiki content yet.

### 5. Page Title Resolution

Items need wiki page titles, which may differ from item names.

**Question**: How do we resolve page titles? Is there a registry method for this?

**Investigation needed**: Check WikiRegistry API.

### 6. Image Names

Templates need image file names (e.g., `[[File:Sword.png]]`).

**Question**: Where do image names come from? Registry? Item field?

### 7. Class Restrictions

Items have class restrictions stored in the `Classes` field (comma-separated string).

**Question**:
- Should we parse this into a list?
- Is there a junction table for class restrictions?
- How should classes be formatted in templates?

### 8. Crafting Data

Items can be crafting ingredients or results.

**Question**:
- Are there repository methods for querying crafting relationships?
- What tables store crafting data?

### 9. DPS Calculation

The {{Item}} template has a `dps` field.

**Question**: How is DPS calculated? `damage / delay`?

## Decisions Made

### Decision 1: Start Simple, Iterate

**Approach**: Implement a minimal ItemPageGenerator that:
1. Generates {{Item}} template for all items
2. Generates {{Fancy-weapon}}, {{Fancy-armor}}, {{Fancy-charm}} for appropriate items
3. Uses hardcoded/empty values for fields we don't have data for yet

**Rationale**: Better to have working infrastructure and fill in details incrementally than to block on complete data access.

### Decision 2: Defer Complex Enrichment

**Approach**: Skip vendor/drop/quest/crafting source enrichment in initial implementation.

**Rationale**:
- Task description says "just generate fresh content"
- Source enrichment requires additional repository queries not yet implemented
- Can be added in future iteration

### Decision 3: Use Existing Item Entity

**Approach**: Work directly with the `Item` domain entity from repository.

**Rationale**: Repository query methods already exist (`get_items_for_wiki_generation()`).

## Implementation Plan

Based on investigation, here's the implementation approach:

1. **ItemPageGenerator.generate_page(item: Item) -> str**
   - Classify item kind using `classify_item_kind()`
   - Generate category tags using `CategoryGenerator`
   - Render appropriate templates based on kind
   - Return complete wikitext

2. **Template Context Building**
   - Create helper methods to build template contexts from Item entities
   - Handle None/missing values gracefully (convert to empty strings)
   - Format boolean fields as "True"/""

3. **Multi-Template Pages** (weapons/armor)
   - For now, generate single-tier templates with base stats
   - Defer multi-tier support until ItemStats repository query exists

4. **Testing Strategy**
   - Unit tests with mock Item entities
   - Verify template rendering
   - Verify category tag generation
   - Test all item kinds
