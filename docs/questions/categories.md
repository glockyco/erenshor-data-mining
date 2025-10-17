# Category Generation Questions

**Date**: 2025-10-17
**Task**: Implement programmatic category tag generation system (Phase 3, Task 1.3)

## Overview

This document captures questions and uncertainties about category generation that need clarification or investigation.

## Questions for Investigation

### 1. What categories actually exist on the wiki?

**Status**: Need to investigate actual wiki pages

Based on Phase 3 analysis document (lines 112-140), the proposed mapping is:

**Item Categories**:
- "Weapons" - for weapon items
- "Armor" - for armor items
- "Charms" - for charm items
- "Auras" - for aura items
- "Ability Books" - for ability book items
- "Consumables" - for consumable items
- "Molds" - for mold items
- "Items" - for general items (fallback)

**Secondary Categories** (multi-category support):
- "Quest Items" - items with quest interactions
- "Craftable" - items that can be crafted
- "Legendary Items" - items with legendary rarity
- "Crafting Materials" - items used in crafting (e.g., molds with template_flag=1)

**Character Categories**:
- Unknown - need to investigate

**Spell/Skill Categories**:
- Unknown - need to investigate

**Action**: Need to check actual wiki to see what categories are in use.

### 2. How do we determine categories from item properties?

**Status**: Partially understood from legacy code

From `item_classifier.py`, items are classified by kind:
- weapon: `required_slot` in {Primary, PrimaryOrSecondary, Secondary}
- armor: equippable slot not in weapon slots, not General, not Aura
- aura: `required_slot` == 'Aura'
- ability_book: `teach_spell` or `teach_skill` present
- consumable: `required_slot` == 'General' AND click effect present AND Disposable=true
- mold: `template_flag` == 1
- general: fallback

**Primary category mapping** (proposed):
```python
{
    "weapon": "Weapons",
    "armor": "Armor",
    "aura": "Auras",
    "ability_book": "Ability Books",
    "consumable": "Consumables",
    "mold": "Molds",
    "general": "Items"
}
```

**Secondary categories** (need to verify properties exist):
- Quest Items: How to detect? Check `assign_quest_on_read` or `complete_on_read`?
- Craftable: How to detect? No clear property in Item model
- Legendary: What property indicates rarity? No `rarity` field in Item model
- Crafting Materials: `template_flag` == 1 (for molds)

**Action**: Verify these properties exist in Item model and are reliable.

### 3. Are there special characters or naming conventions for categories?

**Status**: Assumed standard MediaWiki format

MediaWiki categories use format: `[[Category:CategoryName]]`

**Assumptions**:
- Category names are case-sensitive
- Category names can have spaces
- Multiple categories separated by newlines
- Categories typically placed at end of page

**Action**: Verify this matches wiki conventions.

### 4. Should categories be sorted? Deduplicated?

**Status**: Need to decide

**Proposed behavior**:
- **Deduplication**: YES - use set or check before adding
- **Sorting**: NO - maintain logical order (primary first, then secondary)

**Rationale**: Order might be semantically meaningful (e.g., primary category first).

**Action**: Confirm this is acceptable.

### 5. What if an entity has no categories?

**Status**: Need to decide

**Proposed behavior**:
- Every item gets at least one category (fallback to "Items")
- Better to have a category than none for wiki organization

**Action**: Confirm this approach.

### 6. Are there cross-entity categories?

**Example**: An item that's also a quest item

**Status**: Supported by design

The multi-category support should handle this:
```python
categories = ["Items", "Quest Items"]
```

**Action**: Verify this is the desired behavior.

### 7. Should we validate category names?

**Status**: Need to decide

**Options**:
1. No validation - trust the mapping
2. Validate against known list of categories
3. Log warning for unknown categories

**Proposed**: Option 1 (no validation) - keep it simple
- Categories can be added to wiki dynamically
- No need to maintain a master list
- If category doesn't exist on wiki, it will be created

**Action**: Confirm this approach.

## Decisions Made

### Item Kind to Category Mapping

Based on `item_classifier.py` and Phase 3 analysis:

```python
ITEM_KIND_TO_CATEGORY = {
    "weapon": "Weapons",
    "armor": "Armor",
    "aura": "Auras",
    "ability_book": "Ability Books",
    "consumable": "Consumables",
    "mold": "Molds",
    "general": "Items",
}
```

### Multi-Category Support

Items can have multiple categories:
- Primary category from item kind (always present)
- Secondary categories from properties (optional)

Example: A mold is both "Molds" and "Crafting Materials"

### Category Generation Strategy

1. **Determine item kind** using existing `classify_item_kind()` function
2. **Map to primary category** using `ITEM_KIND_TO_CATEGORY`
3. **Add secondary categories** based on item properties
4. **Deduplicate** using set/list check
5. **Return** list of category names (without `[[Category:...]]` wrapper)

## Implementation Notes

### Item Model Properties Available

From `item.py`:
- `required_slot` - for classification
- `teach_spell`, `teach_skill` - for ability books
- `template` (template_flag) - for molds/crafting
- `item_effect_on_click` - for consumables
- `disposable` - for consumables
- `assign_quest_on_read`, `complete_on_read` - for quest items
- `unique`, `relic` - for special items

### Missing Properties

**Rarity/Quality**: No `rarity` or `quality` field in Item model
- Can't generate "Legendary Items" category without this
- **Decision**: Skip rarity-based categories for now

**Craftable Flag**: No direct `is_craftable` property
- Could check if item appears in crafting recipes (requires join)
- **Decision**: Skip "Craftable" category for now (needs cross-table query)

### Simplified Scope

For initial implementation:
- **Primary categories**: From item kind (7 categories)
- **Secondary categories**:
  - "Quest Items" - if `assign_quest_on_read` or `complete_on_read` is set
  - "Crafting Materials" - if `template == 1` (molds)

**Deferred**:
- "Legendary Items" - needs rarity property
- "Craftable" - needs recipe lookup
- Character categories - focus on items first
- Spell/Skill categories - focus on items first

## Open Questions (Priority Order)

1. ❓ **HIGH**: What categories actually exist on the wiki? (need to check real wiki)
2. ❓ **MEDIUM**: Should "Crafting Materials" only apply to molds, or other items too?
3. ❓ **MEDIUM**: Are quest items the only cross-cutting category?
4. ❓ **LOW**: Should categories be in a specific order?
5. ❓ **LOW**: Should we log when an item has no secondary categories?

## Next Steps

1. Check actual wiki to see what categories exist
2. Implement simplified version with item categories only
3. Add tests with known item examples
4. Extend to other entity types if time permits
5. Document category rules clearly in code

---

**Last Updated**: 2025-10-17
