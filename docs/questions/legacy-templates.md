# Legacy Template Questions

## Investigation Findings

### Current Template Usage (from Jinja2 templates)

**Active templates** currently being generated:
- `{{Item}}` - For all items (item.jinja2)
- `{{Fancy-weapon}}` - For weapon stat tables (weapon.jinja2)
- `{{Fancy-armor}}` - For armor/charm stat tables (armor.jinja2, charm.jinja2)
- `{{Character}}` - For characters (character.jinja2) ⚠️ **CONTRADICTION**
- `{{Spell}}` - For spells (spell.jinja2)

### Contradiction: {{Character}} vs {{Enemy}} ✅ RESOLVED

**Problem**: The phase-3-feedback-analysis-v3.md says:
- `{{Character}}` → `{{Enemy}}` (legacy mapping)
- `{{Pet}}` → `{{Enemy}}`

But the current character.jinja2 template generates `{{Character}}`, not `{{Enemy}}`.

**RESOLUTION** (from research-template-inventory.md):
- **Active template**: `{{Enemy}}` (characters/enemy.j2)
- **Legacy template**: `{{Character}}` (characters/character.j2) - marked as "Currently unused"
- The character.jinja2 template is the LEGACY template
- The enemy.j2 template is the ACTIVE template

**Conclusion**:
- `{{Character}}` → `{{Enemy}}` IS a legacy mapping
- The character.jinja2 template file exists but should NOT be used
- CharacterGenerator uses enemy.j2 (the active template)
- Legacy pages with `{{Character}}` should be migrated to `{{Enemy}}`

### Old Implementation Analysis

**From C# WikiUtils code**:
- Only found `WikiFancyWeapon` and `WikiFancyArmor` classes
- These generate `{{Fancy-weapon}}` and `{{Fancy-armor}}` templates
- NO evidence of `{{Item}}`, `{{Consumable}}`, `{{Weapon}}`, `{{Armor}}`, or `{{Character}}` template generation in WikiUtils
- The old code only handled stat table templates (Fancy-*)

**From Unity export code**:
- ItemListener.cs exports items to database
- CharacterListener.cs exports characters to database
- No wiki template generation in listeners (just database export)

**Conclusion**: The old C# code did NOT generate full wiki pages with `{{Item}}` or `{{Character}}` templates. It only generated stat table templates (`{{Fancy-*}}`).

### Legacy Template Mappings (from phase-3-feedback-analysis-v3.md)

**Items - Replace with {{Item}}**:
1. `{{Weapon}}` → `{{Item}}`
2. `{{Armor}}` → `{{Item}}`
3. `{{Consumable}}` → `{{Item}}`
4. `{{Mold}}` → `{{Item}}`
5. `{{Ability Books}}` → `{{Item}}`
6. `{{Ability_Books}}` → `{{Item}}` (underscore variant)
7. `{{Auras}}` → `{{Item}}`

**Characters - Replace with {{Enemy}}**:
8. `{{Character}}` → `{{Enemy}}`
9. `{{Pet}}` → `{{Enemy}}`

**Remove entirely**:
10. `{{Enemy Stats}}` - Remove completely (replaced by stat tables)

**Keep these (active templates)**:
- `{{Item}}` - For all items
- `{{Fancy-weapon}}` - Weapon stat tables
- `{{Fancy-armor}}` - Armor stat tables
- `{{Fancy-charm}}` - Charm stat tables
- `{{Enemy}}` - For characters (⚠️ contradicts current implementation)

### User Feedback Context

From phase-3-plan-feedback.md (lines 66-82):

> "I don't think we're still using all the (item) templates that you mentioned.
> At the very least, we decided to discontinue Consumable templates and use
> the basic Item templates for those instead. Not sure about molds and ability
> books. Also, Weapon and Armor ONLY use the Fancy-Weapon and Fancy-Armor
> templates - the non-stat-related info (drop location, vendors, ...) use the
> basic {{Item ...}} template."

> "However, we MUST be able to REMOVE such templates from existing wiki pages
> (e.g., replace {{Consumable ...}} with {{Item ...}}). Can also find some of
> this logic in the old implementation. Also, please beware that, e.g., Weapon
> and Armor pages use multiple templates on the same page (one {{Item ...}}
> and three {{Fancy-Weapon ...}} / {{Fancy-Armor ...}} each)."

From phase-3-plan-feedback.md (lines 19-21):

> "Regarding legacy template replacements: please check which ones we already
> had in the old code as well. I know that you missed at least Character -> Enemy
> in the examples you showed."

## Questions for User

### Q1: ✅ Character Template Name - RESOLVED

~~Character template question~~ - RESOLVED via research-template-inventory.md:
- `{{Enemy}}` is the active template
- `{{Character}}` is legacy and should be migrated

### Q2: Field Mapping During Replacement

When replacing legacy templates (e.g., `{{Consumable|name=Potion|type=Food}}` → `{{Item|...}}`):

Do we need field name mapping, or just template name replacement?

**Proposed approach**: Just rename template, keep all fields as-is
- Simpler implementation
- Assumes legacy templates have compatible field names
- If fields don't match, wiki will show empty values (safe failure)
- Can add field mapping later if needed

**Alternative**: Extract via field preservation, then regenerate
- More complex
- Requires knowing field mappings
- More robust but harder to implement

**Question**: Is simple template name replacement sufficient, or do we need field mapping?

### Q3: ✅ Multiple Templates Per Page - RESOLVED

From user feedback (phase-3-plan-feedback.md lines 66-82):
> "Weapon and Armor pages use multiple templates on the same page (one {{Item ...}}
> and three {{Fancy-Weapon ...}} / {{Fancy-Armor ...}} each)"

**Conclusion**:
- Legacy template remover should handle multiple templates per page
- Process each template independently
- Only replace templates that match legacy mappings
- Keep `{{Item}}` and `{{Fancy-*}}` templates untouched
- Preserve template order and position

### Q4: ✅ Fancy-charm vs Fancy-armor - RESOLVED

From actual charm.jinja2 file:
- Charm template generates `{{Fancy-charm}}` ✓

**Conclusion**:
- `{{Fancy-charm}}` is the active template for charms
- `{{Fancy-armor}}` is the active template for armor
- Both are separate templates (as expected)

### Q5: Ability Books Template Name

From research-template-inventory.md:
- Template: `{{Ability Books}}` (with space)

From phase-3-feedback-analysis-v3.md legacy mappings:
- `{{Ability Books}}` → `{{Item}}`
- `{{Ability_Books}}` → `{{Item}}` (underscore variant)

**Question**: Is `{{Ability Books}}` actually a legacy template that should be migrated to `{{Item}}`, or is it still active?

The research doc says ability_book.j2 generates `{{Ability Books}}`, which suggests it's still active.

But the legacy mapping says it should migrate to `{{Item}}`.

**Need clarification**:
- Is `{{Ability Books}}` active or legacy?
- Should we keep generating it or migrate to `{{Item}}`?

### Q6: Mold Template Name

Similar question for Molds:

From research-template-inventory.md:
- Template: `{{Mold}}`

From phase-3-feedback-analysis-v3.md:
- `{{Mold}}` → `{{Item}}`

**Need clarification**: Is `{{Mold}}` active or legacy?

## Summary: Templates Status

### Confirmed Active Templates
- `{{Item}}` - For all items ✓
- `{{Fancy-weapon}}` - Weapon stat tables ✓
- `{{Fancy-armor}}` - Armor stat tables ✓
- `{{Fancy-charm}}` - Charm stat tables ✓
- `{{Enemy}}` - For characters (NPCs, enemies, bosses) ✓
- `{{Ability}}` - For spells and skills ✓

### Confirmed Legacy Templates (Need Removal)
- `{{Character}}` → `{{Enemy}}` ✓
- `{{Pet}}` → `{{Enemy}}` ✓
- `{{Consumable}}` → `{{Item}}` ✓ (user confirmed: "discontinue Consumable templates")
- `{{Weapon}}` → `{{Item}}` (probably legacy, weapons use {{Fancy-weapon}})
- `{{Armor}}` → `{{Item}}` (probably legacy, armor uses {{Fancy-armor}})
- `{{Enemy Stats}}` - Remove entirely ✓
- `{{Auras}}` → `{{Item}}` (probably legacy, auras use {{Item}} now)

### Uncertain Templates (Need User Clarification)
- `{{Mold}}` → `{{Item}}` OR keep as active? (user: "Not sure about molds")
- `{{Ability Books}}` → `{{Item}}` OR keep as active? (user: "Not sure about ability books")
- `{{Ability_Books}}` → Same as above (underscore variant)

## Implementation Approach

Based on findings, here's the proposed approach:

### Simple Template Name Replacement

**Strategy**: Just replace template names, don't map fields.

**Reasoning**:
1. Legacy templates likely have similar field names to new templates
2. Field preservation system (Task 2.3) already handles field extraction
3. Simpler implementation = fewer bugs
4. Can add field mapping later if needed

### Implementation Plan

1. **LegacyTemplateRemover class**:
   - `remove_legacy_templates(wikitext: str) -> str`
   - Uses TemplateParser to find/replace templates
   - Template name mappings (10 legacy → 4 active)
   - Preserves template parameters (just renames template)

2. **Configuration**:
   ```python
   LEGACY_MAPPINGS = {
       "Weapon": "Item",
       "Armor": "Item",
       "Consumable": "Item",
       "Mold": "Item",
       "Ability Books": "Item",
       "Ability_Books": "Item",
       "Auras": "Item",
       "Character": "Enemy",  # ⚠️ Need to clarify Q1
       "Pet": "Enemy",
   }

   TEMPLATES_TO_REMOVE = [
       "Enemy Stats",
   ]
   ```

3. **Algorithm**:
   ```
   for each legacy template name in mappings:
       find all templates with that name
       for each template:
           extract parameters
           if in TEMPLATES_TO_REMOVE:
               remove template entirely
           else:
               replace with new template name, same parameters
   ```

### Edge Cases to Handle

1. **Nested templates**: TemplateParser handles this
2. **Multiple templates per page**: Process each independently
3. **Template with complex parameters**: Preserve as-is
4. **Malformed templates**: Log warning, skip

## Next Steps

1. Wait for user clarification on questions (especially Q1)
2. Implement LegacyTemplateRemover with simple name replacement
3. Write comprehensive unit tests
4. Test on example wiki pages (if available)
