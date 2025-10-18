# Field Preservation System - Questions & Findings

## Analysis of Old Implementation

After examining the old C# code, I found the following:

### What Fields Were Actually Preserved?

**Answer: NONE directly in the codebase.**

The old implementation had:
1. `WikiFancyWeaponFactory.Create(string wikiString)` - Parses existing wiki page
2. `WikiFancyWeaponFactory.Create(ItemRecord, ItemStatsRecord)` - Generates from database
3. `ObjectComparer.Compare<T>()` - Compares two objects marked with `[UseForComparison]`

**Key finding**: The comparison system existed to DETECT differences, not to preserve fields. The `OriginalWikiString` property was stored but never used for merging.

### Use Case Discovery

Looking at `ItemListener.cs` (line 49):
```csharp
itemStatsRecord.WikiString = _weaponFactory.Create(itemRecord, itemStatsRecord).ToString();
```

The code always generates fresh wiki strings from database - no merging with existing wiki content.

### The Real Use Case

The comparison tools (`ObjectComparer`, `UseForComparison` attribute) appear to be for:
- **Manual review** in Unity Editor
- **Detecting what changed** between game versions
- **NOT for automated field preservation**

## Questions

### 1. What fields actually need preservation?

**Finding**: Based on the templates and user feedback, likely candidates are:
- `description` - Manual lore/flavor text added by wiki editors
- `image` / `imagecaption` - Custom images or captions
- Source fields (`vendorsource`, `source`, `othersource`, `questsource`, etc.) - Manually researched content

**Question**: Should we start with just these, or are there others?

### 2. Different rules for different templates?

**Answer**: YES - Template-specific rules are essential.

Templates have different preservation needs:
- `{{Item}}`: Preserve `description`, `image`, source fields
- `{{Fancy-weapon}}`: Preserve `description` (item lore), maybe `image`
- `{{Fancy-armor}}`: Same as fancy-weapon
- `{{Character}}`: Unknown (need to examine)
- `{{Ability}}`: Unknown (need to examine)

### 3. How should custom handlers be registered?

**Proposed approach**:
```python
# Built-in handlers
def override_handler(old_value, new_value, context):
    return new_value

def preserve_handler(old_value, new_value, context):
    return old_value

def prefer_manual_handler(old_value, new_value, context):
    return old_value if old_value and old_value.strip() else new_value

# Custom handler registration
preservation_config.register_handler("my_custom", my_handler_func)
```

### 4. Where should configuration live?

**Options**:
1. **TOML file** (`config/field-preservation.toml`) - User-editable, version controlled
2. **Python constants** - Simple, type-safe, but requires code changes
3. **Database table** - Overkill for this use case

**Recommendation**: Start with Python constants (simple dict in the module), provide path to migrate to TOML if user wants runtime configuration.

Example:
```python
DEFAULT_PRESERVATION_RULES = {
    "Item": {
        "description": "preserve",
        "image": "prefer_manual",
        "imagecaption": "prefer_manual",
        "vendorsource": "preserve",
        "source": "preserve",
        "othersource": "preserve",
        "questsource": "preserve",
        "relatedquest": "preserve",
        "craftsource": "preserve",
        "componentfor": "preserve",
        # All other fields: implicit "override" (default)
    },
    "Fancy-weapon": {
        "description": "preserve",
        "image": "prefer_manual",
        "name": "prefer_manual",
    },
    "Fancy-armor": {
        "description": "preserve",
        "image": "prefer_manual",
        "name": "prefer_manual",
    },
}
```

### 5. How to handle fields that don't exist in old page?

**Answer**: New fields always use database value (no old value to preserve).

This is handled naturally by the `prefer_manual_handler` - if old_value is empty/None, use new value.

## Implementation Plan

Based on findings, implement:

1. **Module**: `src/erenshor/application/generators/field_preservation.py`

2. **Components**:
   - `FieldPreservationConfig` - Loads rules from dict/TOML
   - `FieldPreservationHandler` - Applies rules to templates
   - Built-in handlers: `override`, `preserve`, `prefer_manual`
   - Handler registry for custom handlers

3. **Configuration**: Start with Python dict constants (easy to migrate to TOML later)

4. **Integration**:
   - `PageGeneratorBase` gets `apply_field_preservation()` method
   - Generators call this before returning final wikitext
   - Works with `TemplateParser` to extract/update fields

5. **Tests**: Comprehensive unit tests for all handlers and edge cases

## Open Questions for User

1. **Source enrichment fields**: Are these the main fields that need preservation?
2. **Template coverage**: Should we implement for all templates, or start with Item/Fancy-weapon/Fancy-armor?
3. **Configuration format**: Python dict OK for now, or should we go straight to TOML?
4. **Custom handlers**: Do you foresee needing custom handlers beyond the 3 built-in ones?
