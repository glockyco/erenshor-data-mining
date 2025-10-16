# Stable Entity ID Research for Wiki Registry

**Created**: 2025-10-16  
**Purpose**: Analyze and propose stable ID strategies for tracking game entities across version updates

## Executive Summary

This document analyzes the current entity identification system and proposes stable ID strategies for the wiki registry system. The goal is to detect renamed/changed entities across game versions while minimizing false positives and false negatives.

### Current System Analysis

The registry currently uses two ID types:
- **uid**: `{type}:{db_id}` - Database row identifier (changes when structure changes)
- **stable_key**: `{type}:{resource_name}` - Falls back to `{type}:{db_name}` when resource_name unavailable

**Problem**: Resource names and display names can both change across game versions, making entity tracking unreliable.

---

## Entity-by-Entity Analysis

### 1. Items

#### Available Fields
From `ItemRecord.cs` and `ItemListener.cs`:
- **Id** (string, PrimaryKey): Item.Id from ScriptableObject
- **ItemName** (string): Display name (user-facing, may change)
- **ResourceName** (string): ScriptableObject asset filename
- **ItemDBIndex** (int): Index in Resources.LoadAll array

#### Current Strategy
```python
EntityRef(
    entity_type=EntityType.ITEM,
    db_id=item.Id,           # Unity-assigned ID
    db_name=item.ItemName,   # Display name
    resource_name=item.ResourceName  # Asset filename
)
```

**stable_key**: `item:{ResourceName}`

#### Analysis

**Strengths**:
- `Id` field appears to be Unity's ScriptableObject identifier
- `ResourceName` is the asset filename, relatively stable
- Items have clear identity throughout codebase

**Weaknesses**:
- ResourceName can change if developer renames files
- Id might change if ScriptableObject is recreated
- ItemName definitely changes (many examples in mapping.json)

**Stability Assessment**: **MEDIUM-HIGH**

#### Recommended Strategy

**Primary**: `item:{Id}`
- Unity ScriptableObject IDs are stable unless asset is deleted/recreated
- Most reliable for tracking same conceptual item

**Fallback 1**: `item:{ResourceName}`
- Current approach, reasonable fallback
- Survives display name changes

**Fallback 2**: `item:{ItemName}` (display name matching)
- Last resort for detecting renames
- Use fuzzy matching to detect similar names

**Detection Logic**:
```python
# Detect rename if:
# - Id matches but ResourceName or ItemName changed
# - ResourceName matches but Id changed (file moved/recreated)
# - High similarity between ItemNames (Levenshtein distance < 3)
```

**Risk Level**: **LOW**
- Items appear to have consistent IDs
- Clear file structure in Unity

---

### 2. Characters

#### Available Fields
From `CharacterRecord.cs` and `CharacterListener.cs`:
- **Id** (int, PrimaryKey, auto-increment): Database row ID
- **Guid** (string, Indexed): Unity prefab GUID (for prefabs) or scene instance ID
- **ObjectName** (string): GameObject name in Unity scene
- **NPCName** (string): Display name (user-facing, may change)
- **IsPrefab** (bool): Whether it's a prefab or scene-placed instance
- **Scene** (string): Scene name (for non-prefabs)
- **X, Y, Z** (float): Coordinates (for non-prefabs)

#### Current Strategy
```python
# From EntityRef.from_character()
if char.IsPrefab and char.ObjectName:
    resource_name = char.ObjectName  # Prefab name only
else:
    # Non-prefab: composite key with coordinates
    resource_name = f"{char.ObjectName}|{scene}|{x:.2f}|{y:.2f}|{z:.2f}"

EntityRef(
    entity_type=EntityType.CHARACTER,
    db_id=char.Guid,           # Prefab GUID or scene instance
    db_name=char.NPCName,      # Display name
    resource_name=resource_name
)
```

**stable_key**: `character:{resource_name}`

#### Analysis

**Strengths**:
- Guid distinguishes prefabs reliably (Unity prefab GUID)
- Coordinate-based keys for scene instances handle unique placements
- Clear distinction between prefab and instance

**Weaknesses**:
- **Critical Issue**: ObjectName can change (see mapping.json examples)
  - "Lost Sea Giant" vs "Lost Sea Giant Female" → same wiki page
  - "A Highwayman Raider" vs "A Highwayman Raider (1)" → same wiki page
- **Guid for scene instances is unstable**: `"scene:{sceneName}:{GetInstanceID()}"`
  - Instance IDs change when Unity scenes are reloaded/reorganized
  - NOT suitable as stable identifier
- Coordinates may shift slightly with terrain updates
- NPCName definitely changes (many examples in mapping.json)

**Stability Assessment**: **MEDIUM for Prefabs, LOW for Scene Instances**

#### Recommended Strategy

**For Prefabs (IsPrefab=true)**:

**Primary**: `character:{Guid}`
- Unity prefab GUIDs are stable across versions
- Best identifier for prefab entities

**Fallback**: `character:{ObjectName}` (prefab name)
- Handles GUID changes if prefab is recreated
- Still relatively stable

**For Scene Instances (IsPrefab=false)**:

**Primary**: `character:{ObjectName}|{Scene}|{X}|{Y}|{Z}` (current approach)
- Coordinates provide unique identifier
- Problem: ObjectName can change, coordinates can shift

**Alternative**: Use NPCName+Scene+Coordinates
- `character:{NPCName}|{Scene}|{X}|{Y}|{Z}`
- Problem: NPCName changes more frequently

**RECOMMENDATION**: 
1. For prefabs: Use Guid primarily, ObjectName as fallback
2. For scene instances: Accept manual mapping requirement
   - Scene instance IDs are inherently unstable
   - Coordinate-based matching is best effort
   - Rely on manual mapping.json entries for important NPCs

**Detection Logic**:
```python
# Prefab detection:
# - Guid matches but ObjectName or NPCName changed → rename detected
# - ObjectName matches but Guid changed → prefab recreated

# Scene instance detection:
# - Coordinate proximity match (within 1.0 units) + Scene + NPCName similarity
# - Flag for manual review if multiple candidates
```

**Risk Level**: **MEDIUM for Prefabs, HIGH for Scene Instances**
- Prefabs have stable GUIDs
- Scene instances are inherently unstable (Unity limitation)

---

### 3. Spells

#### Available Fields
From `SpellRecord.cs` and `SpellListener.cs`:
- **SpellDBIndex** (int, PrimaryKey): Index in Resources.LoadAll array
- **Id** (string): Spell.Id from BaseScriptableObject
- **SpellName** (string): Display name (user-facing, may change)
- **ResourceName** (string): ScriptableObject asset name

#### Current Strategy
```python
EntityRef(
    entity_type=EntityType.SPELL,
    db_id=spell.Id,              # Unity-assigned ID
    db_name=spell.SpellName,     # Display name
    resource_name=spell.ResourceName  # Asset filename
)
```

**stable_key**: `spell:{ResourceName}`

#### Analysis

**Strengths**:
- Similar to Items (ScriptableObject-based)
- ResourceName provides stable filename reference
- Id field appears stable

**Weaknesses**:
- Many spell variants share functionality (see mapping.json):
  - "DRU - Greater Regrowth (Cast)" vs "DRU - Greater Regrowth (Effect)"
  - "DUEL - Deathly Embrace" vs "Death's Embrace (Caster)"
- ResourceName can change with file reorganization
- SpellName definitely changes (typo fixes, etc.)

**Stability Assessment**: **MEDIUM-HIGH**

#### Recommended Strategy

**Primary**: `spell:{Id}`
- Most stable identifier
- Survives file renames

**Fallback**: `spell:{ResourceName}`
- Current approach, reasonable
- Handles Id changes if asset recreated

**Detection Logic**:
```python
# Detect rename if:
# - Id matches but ResourceName or SpellName changed
# - ResourceName matches but Id changed
# - High similarity in SpellName (Levenshtein distance < 3)
# - Same Line + Type + similar effect values
```

**Risk Level**: **LOW**
- Similar stability to Items

---

### 4. Skills

#### Available Fields
From `SkillRecord.cs`:
- **SkillDBIndex** (int, PrimaryKey): Index in Resources.LoadAll array
- **Id** (string): Skill.Id from BaseScriptableObject  
- **SkillName** (string): Display name
- **ResourceName** (string): ScriptableObject asset name

#### Current Strategy
```python
EntityRef(
    entity_type=EntityType.SKILL,
    db_id=skill.Id,              # Unity-assigned ID
    db_name=skill.SkillName,     # Display name
    resource_name=skill.ResourceName  # Asset filename
)
```

**stable_key**: `skill:{ResourceName}`

#### Analysis

**Identical to Spells** - same ScriptableObject pattern

**Stability Assessment**: **MEDIUM-HIGH**

#### Recommended Strategy

**Primary**: `skill:{Id}`
**Fallback**: `skill:{ResourceName}`

**Risk Level**: **LOW**

---

### 5. Quests

#### Available Fields
From `QuestRecord.cs`:
- **QuestDBIndex** (int, PrimaryKey): Index in Resources.LoadAll array
- **QuestName** (string): Display name
- **DBName** (string): Unique identifier field
- **ResourceName** (string): ScriptableObject asset name

#### Current Strategy
Not yet implemented in EntityRef, but would follow pattern:
```python
EntityRef(
    entity_type=EntityType.QUEST,
    db_id=quest.DBName,          # Quest's internal unique ID
    db_name=quest.QuestName,     # Display name
    resource_name=quest.ResourceName  # Asset filename
)
```

#### Analysis

**Strengths**:
- **DBName field** appears to be explicitly designed as unique identifier
- ResourceName provides fallback
- Quests are content (less likely to be renamed)

**Stability Assessment**: **HIGH**

#### Recommended Strategy

**Primary**: `quest:{DBName}`
- Explicitly designed as unique identifier
- Most stable option

**Fallback**: `quest:{ResourceName}`

**Risk Level**: **VERY LOW**
- DBName field suggests developer intent for stable IDs

---

### 6. Factions

#### Available Fields
From `WorldFactionRecord.cs` (inferred from usage):
- **REFNAME** (string): Reference name (stable identifier)
- **FactionDesc** (string): Display name

#### Current Strategy
```python
EntityRef(
    entity_type=EntityType.FACTION,
    db_id=None,                      # No DB ID
    db_name=faction.FactionDesc,     # Display name
    resource_name=faction.REFNAME    # Reference name
)
```

**stable_key**: `faction:{REFNAME}`

#### Analysis

**Strengths**:
- **REFNAME explicitly designed as stable reference**
- Used throughout codebase for lookups
- Clear intent from naming

**Weaknesses**:
- FactionDesc can change (see mapping.json: "the Torchbearers" typo fix)

**Stability Assessment**: **VERY HIGH**

#### Recommended Strategy

**Primary**: `faction:{REFNAME}`
- Already optimal
- Explicitly designed for stability

**No fallback needed** - REFNAME is the stable identifier

**Risk Level**: **VERY LOW**

---

## Summary Table

| Entity Type | Recommended Primary Key | Fallback Key | Stability | Risk Level | Notes |
|-------------|------------------------|--------------|-----------|------------|-------|
| **Items** | `item:{Id}` | `item:{ResourceName}` | Medium-High | Low | Id is Unity ScriptableObject identifier |
| **Characters (Prefab)** | `character:{Guid}` | `character:{ObjectName}` | Medium | Medium | Guid is Unity prefab GUID |
| **Characters (Scene)** | `character:{ObjectName}\|{Scene}\|{X}\|{Y}\|{Z}` | Manual mapping required | Low | High | Scene instances inherently unstable |
| **Spells** | `spell:{Id}` | `spell:{ResourceName}` | Medium-High | Low | Same pattern as Items |
| **Skills** | `skill:{Id}` | `skill:{ResourceName}` | Medium-High | Low | Same pattern as Items |
| **Quests** | `quest:{DBName}` | `quest:{ResourceName}` | High | Very Low | DBName explicitly designed as unique ID |
| **Factions** | `faction:{REFNAME}` | None needed | Very High | Very Low | Already optimal |

---

## Implementation Recommendations

### 1. Update EntityRef Construction

**Refactor from_* methods to use recommended keys:**

```python
@classmethod
def from_item(cls, item: Any) -> "EntityRef":
    """Create from database item."""
    return cls(
        entity_type=EntityType.ITEM,
        db_id=item.Id,                  # Use Id as primary stable identifier
        db_name=item.ItemName,
        resource_name=item.ResourceName  # Keep as fallback
    )
```

**Update stable_key property:**

```python
@property
def stable_key(self) -> str:
    """Key for tracking entities across versions (prefers db_id)."""
    # Prefer db_id for stability (Id for Items/Spells/Skills, Guid for Characters, etc.)
    if self.db_id is not None:
        return f"{self.entity_type.value}:{self.db_id}"
    # Fallback to resource_name
    if self.resource_name:
        return f"{self.entity_type.value}:{self.resource_name}"
    # Last resort: display name
    return f"{self.entity_type.value}:{self.db_name}"
```

### 2. Build EntityRef with Proper Precedence

**Key principle**: stable_key should prefer the most stable identifier available.

**Current Problem**: 
- `uid` uses db_id (good)
- `stable_key` prefers resource_name (less stable than Id/Guid/DBName)

**Solution**:
- Make db_id the primary stable identifier
- Use resource_name as fallback only

### 3. Migration Strategy

**Phase 1: Update stable_key generation (backward compatible)**
- Change stable_key property to prefer db_id
- Maintain resource_name fallback
- Registry can still load old keys

**Phase 2: Registry migration script**
- Read existing registry.json
- For each entity, look up by old stable_key
- Create new stable_key using db_id
- Update manual_mappings dict keys
- Save with both old and new keys for transition period

**Phase 3: Clean up deprecated keys**
- After validation, remove old stable_key format
- Keep only db_id-based keys

### 4. Rename Detection Algorithm

```python
def detect_renames(old_registry: WikiRegistry, new_registry: WikiRegistry) -> List[RenameCandidate]:
    """Detect potential entity renames between registry versions."""
    
    candidates = []
    
    # Strategy 1: Match by primary key (db_id), check for name changes
    for new_entity in new_registry.all_entities():
        old_entity = old_registry.find_by_db_id(new_entity.db_id)
        
        if old_entity:
            if old_entity.db_name != new_entity.db_name:
                # Primary ID matches but name changed → likely rename
                candidates.append(RenameCandidate(
                    old=old_entity,
                    new=new_entity,
                    confidence="high",
                    reason="Primary ID match, name changed"
                ))
    
    # Strategy 2: Match by fallback key (resource_name), check for ID changes
    for new_entity in new_registry.all_entities():
        if new_entity.resource_name:
            old_entity = old_registry.find_by_resource_name(new_entity.resource_name)
            
            if old_entity and old_entity.db_id != new_entity.db_id:
                # Resource name matches but ID changed → asset recreated
                candidates.append(RenameCandidate(
                    old=old_entity,
                    new=new_entity,
                    confidence="medium",
                    reason="Resource name match, ID changed (asset recreated?)"
                ))
    
    # Strategy 3: Fuzzy matching on display names (low confidence)
    for new_entity in new_registry.unmatched_entities():
        for old_entity in old_registry.unmatched_entities():
            if similar_names(old_entity.db_name, new_entity.db_name):
                candidates.append(RenameCandidate(
                    old=old_entity,
                    new=new_entity,
                    confidence="low",
                    reason=f"Name similarity: {similarity_score}"
                ))
    
    return candidates
```

### 5. Handle Special Cases

**Characters (Scene Instances)**:
- Accept that they're inherently unstable
- Provide tooling for manual mapping
- Consider warning users about scene instance changes

**Spell/Skill Variants**:
- Detect related spells (same name prefix)
- Group for review (e.g., "Cast" vs "Effect" variants)
- Suggest merge candidates

**Items with Quality Variants**:
- Not an issue (variants stored in ItemStats table, share same Item.Id)

---

## Migration Considerations

### Backward Compatibility

**Challenge**: Existing mapping.json uses current stable_key format:
```json
"character:Brackish Crocodile": { ... }  // Uses ObjectName
"item:GEN - Scribbles of a mad priest 1": { ... }  // Uses ResourceName
```

**Solution**: Support both formats during migration:
1. Load old mapping.json with resource_name-based keys
2. Convert to new db_id-based keys
3. Maintain lookup index for both formats temporarily
4. Gradually phase out old format

### Data Migration Script

```python
def migrate_mapping_json(old_mapping: dict, db_engine) -> dict:
    """Convert mapping.json from resource_name keys to db_id keys."""
    
    new_mapping = {"rules": {}}
    
    for old_key, rule in old_mapping["rules"].items():
        entity_type, old_identifier = old_key.split(":", 1)
        
        # Look up entity in database by resource_name or db_name
        entity = lookup_entity(db_engine, entity_type, old_identifier)
        
        if entity:
            # Create new key using db_id
            new_key = f"{entity_type}:{entity.db_id}"
            new_mapping["rules"][new_key] = rule
        else:
            # Keep old key if entity not found (manual review needed)
            new_mapping["rules"][old_key] = rule
            log_warning(f"Could not migrate key: {old_key}")
    
    return new_mapping
```

---

## Known Risks and Mitigation

### Risk 1: Unity Asset Recreation

**Scenario**: Developer deletes and recreates a ScriptableObject
**Impact**: Id/Guid changes even though conceptual entity is the same
**Mitigation**: 
- Maintain ResourceName fallback matching
- Detect similar entities in new version (name + stats similarity)
- Flag for manual review

### Risk 2: Coordinate Drift (Character Scene Instances)

**Scenario**: Terrain updates cause NPC positions to shift
**Impact**: Coordinate-based keys no longer match
**Mitigation**:
- Use fuzzy coordinate matching (within 1.0-5.0 unit radius)
- Combine with Scene + NPCName for better matching
- Accept manual mapping as primary solution

### Risk 3: Bulk Renames

**Scenario**: Developer does mass file reorganization
**Impact**: Many ResourceName changes at once
**Mitigation**:
- Batch rename detection
- Show summary of all detected changes
- Require confirmation before applying

### Risk 4: False Positives

**Scenario**: Fuzzy matching suggests wrong entity pairing
**Impact**: Wiki pages incorrectly merged or remapped
**Mitigation**:
- Use confidence levels (high/medium/low)
- Require manual confirmation for medium/low confidence
- Provide undo mechanism

---

## Recommended Next Steps

1. **Update EntityRef.from_* methods** to use db_id as primary identifier
2. **Update stable_key property** to prefer db_id over resource_name  
3. **Create migration script** for existing registry.json and mapping.json
4. **Implement rename detection algorithm** with confidence levels
5. **Add CLI commands**:
   - `erenshor registry detect-renames` - Show rename candidates
   - `erenshor registry migrate` - Migrate to new stable_key format
   - `erenshor registry validate` - Check for inconsistencies
6. **Test with playtest variant** before deploying to main
7. **Document new stable_key format** in CLAUDE.md

---

## Conclusion

**Key Insight**: The database already contains stable identifiers (Id, Guid, DBName, REFNAME) that are more reliable than resource_name or db_name. We should use these as primary keys.

**Recommended Approach**:
- Items/Spells/Skills: Use `Id` field (Unity ScriptableObject ID)
- Characters (Prefab): Use `Guid` field (Unity Prefab GUID)
- Characters (Scene): Accept instability, rely on manual mapping
- Quests: Use `DBName` field (explicit unique identifier)
- Factions: Keep using `REFNAME` (already optimal)

**Migration Path**:
1. Update stable_key generation (backward compatible)
2. Migrate existing data
3. Validate against current wiki state
4. Deploy to production

**Risk Assessment**: LOW-MEDIUM
- Most entity types have stable identifiers available
- Scene-placed characters remain a challenge (Unity limitation)
- Manual mapping.json remains essential safety net

