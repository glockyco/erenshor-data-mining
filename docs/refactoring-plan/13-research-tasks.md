# Research Tasks for AI

**Document Status**: TO DO - Assigned to AI
**Date**: 2025-10-16
**Purpose**: Tasks requiring AI investigation and recommendations before implementation can begin

---

## Overview

These are research tasks that the AI (Claude) must complete before Phase 1 implementation can begin. Each task requires analysis, investigation, or design work, with concrete deliverables expected.

**Priority**: **CRITICAL** - Phase 1 cannot start until these are complete.

---

## Task 1: Stable Entity IDs Analysis

**Priority**: CRITICAL BLOCKER

**Assigned To**: AI (Claude)

**User Request**: Q1.3 - "I'm afraid changes of some columns are quite rare. What do you think should be stable columns?"

**Context**: Need to track entities across game versions to detect renames, additions, deletions. Current system is brittle.

**Requirements**:
1. User will provide 2-3 database backups from different game versions
2. Analyze what columns/fields remain stable across versions
3. Recommend stable identifier strategy for each entity type

**Deliverables**:

### 1.1 Stability Analysis Report

For each entity type (Items, Characters, Spells, Skills, etc.):

**Format**:
```markdown
### Items
**Columns Analyzed**: ItemName, ResourceName, Id, Slot, RequiredLevel, ...
**Stable Columns** (never change for same entity):
  - ResourceName (100% stable across versions)
  - Slot + RequiredLevel + BaseStats hash (99% stable)

**Unstable Columns** (can change):
  - ItemName (5% changed - renames)
  - Id (regenerated every export)
  - Description (10% changed)

**Rename Detection**: 12 renames detected via ResourceName match + ItemName change

**Recommended UID Strategy**:
  entity_type/resource_name  (e.g., "item/prefab_sword_001")

**Fallback Strategy** (if ResourceName missing):
  entity_type/composite_key  (e.g., "item/MainHand_10_hash123")
```

**Run this for**:
- Items
- Characters
- Spells
- Skills
- Quests (if data available)
- Zones (if data available)
- Factions (if data available)
- Any other entity types in database

### 1.2 Recommended Implementation

Provide concrete Python code for stable UID generation:

```python
def compute_entity_uid(entity: DbItem) -> str:
    """Compute stable UID for item entity."""
    # Use ResourceName if available (most stable)
    if entity.ResourceName:
        return f"item/{entity.ResourceName}"

    # Fallback to composite key
    composite = f"{entity.Slot}|{entity.RequiredLevel}|{content_hash(entity)}"
    return f"item/{hashlib.sha256(composite.encode()).hexdigest()[:16]}"
```

### 1.3 Edge Cases

Document how to handle:
- Entities with no stable identifier
- Duplicate identifiers (if any found)
- Renamed entities (how to detect and migrate registry)
- New entities (how to add to registry)
- Deleted entities (how to mark in registry)

**User Dependency**: User must provide 2-3 database backups before this task can be completed.

**Time Estimate**: 2-3 days (after backups provided)

---

## Task 2: Managed Templates Inventory

**Priority**: CRITICAL BLOCKER

**Assigned To**: AI (Claude)

**User Request**: Q1.1 - "Please check out the current implementation."

**Context**: Need to know which MediaWiki templates are currently auto-generated to implement template-based content merging.

**Requirements**:
1. Review current implementation (Python generators, Jinja2 templates)
2. Identify all templates currently auto-generated
3. Map templates to entity types

**Deliverables**:

### 2.1 Complete Template Inventory

**Format**:
```markdown
### Items
**Templates**:
- `{{Item Infobox}}` - Always generated
- `{{Loot Table}}` - Generated if item is dropped by mobs
- `{{Vendor Table}}` - Generated if item sold by vendors

### Characters
**Templates**:
- `{{Character Infobox}}` (or `{{Enemy Infobox}}`) - Always generated
- `{{Spawn Locations}}` - Generated if character has spawn points
- `{{Abilities}}` - Generated if character has spells/skills

### Spells
**Templates**:
- `{{Spell Infobox}}` (or `{{Ability Infobox}}`) - Always generated
- `{{Items with Effect}}` - Generated if items proc this spell

### Skills
**Templates**:
- `{{Skill Infobox}}` - Always generated

... (etc for all entity types)
```

### 2.2 Template Structure Analysis

For each template, document:
- Template parameters (what fields does it have?)
- Which database columns map to which template parameters?
- Are there any special rendering rules?
- Are there nested templates?

**Example**:
```markdown
### {{Item Infobox}}
**Parameters**:
- name: Item display name (Items.ItemName)
- image: Item icon (Items.ResourceName + ".png")
- slot: Equipment slot (Items.Slot)
- level: Required level (Items.RequiredLevel)
- stats: Item stats (complex rendering)
... (full list)

**Special Rules**:
- Stats are rendered as nested template {{Stat|stat=value}}
- Classes list is comma-separated
```

### 2.3 Future Template Plan

Based on user feedback (Q1.2): "Future plans also include plain text sections."

**Document**:
- Which plain text sections will be auto-generated in future?
- How should they be structured?
- Which sections should remain manual?

**Proposed Structure** (for user approval):
```markdown
### Character Page Sections (Future)

**Auto-Generated Sections**:
- Overview (brief description from NPC dialog or generated)
- Statistics (stats table)
- Spawn Locations (spawn table with coordinates)
- Loot (drop table)
- Abilities (spell/skill list)

**Manual Sections** (always preserved):
- Strategy (player-written combat tips)
- Trivia (player-written lore/notes)
- Gallery (player-uploaded images)
```

**Time Estimate**: 1-2 days

---

## Task 3: Cargo Integration Analysis

**Priority**: HIGH (User explicitly asked)

**Assigned To**: AI (Claude)

**User Request**: "Speaking of infoboxes: the wiki team has long wanted to introduce Cargo to the wiki (the extension is available already), but we've only done some very small-scale manual testing. How to properly integrate cargo? Should that be considered in some way in our new architecture as well?"

**Context**: MediaWiki Cargo extension stores template data in database tables for querying.

**Requirements**:
1. Explain what Cargo is and how it works
2. Analyze integration with our auto-generated templates
3. Recommend implementation approach
4. Assess if architectural changes needed

**Deliverables**:

### 3.1 Cargo Explanation

**What is Cargo?**
- MediaWiki extension for structured data storage
- Templates declare schema, data stored in DB tables
- Enables SQL-like queries on wiki content
- Allows dynamic lists/tables generated from wiki data

**How it works**:
```wiki
{{#cargo_declare:
  _table=Items
  |name=String
  |level=Integer
  |slot=String
}}

{{#cargo_store:
  _table=Items
  |name={{{name|}}}
  |level={{{level|}}}
  |slot={{{slot|}}}
}}
```

### 3.2 Integration Analysis

**Questions to answer**:
1. Do our current templates work with Cargo? (Check template structure)
2. Do we need to modify templates to declare/store Cargo data?
3. Can we auto-generate Cargo declarations/stores?
4. Would Cargo storage duplicate our SQLite database?
5. What are benefits of Cargo for Erenshor wiki?

**Compatibility Check**:
- Review current `{{Item Infobox}}`, `{{Character Infobox}}`, etc.
- Check if they have Cargo declarations
- Assess what changes needed for Cargo support

### 3.3 Recommended Approach

**Option A: Add Cargo to Existing Templates**
- Modify template generation to include Cargo declarations
- Auto-generate `cargo_declare` and `cargo_store` calls
- Templates remain backward compatible

**Option B: Separate Cargo Templates**
- Keep existing templates unchanged
- Generate separate Cargo storage templates
- Include both in page generation

**Option C: Don't Use Cargo**
- Assess if Cargo provides enough value
- Maybe SQLite database + Google Sheets already provide needed functionality

**Recommendation**: Pick one option and justify.

### 3.4 Implementation Plan

If recommending Cargo integration:

**Phase 1**: Add Cargo support to one entity type (e.g., Items)
**Phase 2**: Validate with wiki team, gather feedback
**Phase 3**: Extend to other entity types
**Phase 4**: Implement dynamic queries/lists

**If NOT recommending Cargo**: Explain why and what alternatives exist.

### 3.5 Architectural Impact

**Changes needed** (if any):
- Template generation code
- Config schema (Cargo table definitions)
- Testing (validate Cargo data storage)

**Scope**: Is this part of initial rewrite or backlog item?

**Time Estimate**: 1-2 days (research + recommendation)

---

## Task 4: Test Database Best Practices

**Priority**: MEDIUM (Can defer to Phase 6)

**Assigned To**: AI (Claude)

**User Request**: Q2.14 - "What do you think is a good / 'best-practice' solution here?"

**Context**: Should test database (~20 MB) be committed to git or regenerated on demand?

**Requirements**:
Research best practices and provide recommendation.

**Deliverables**:

### 4.1 Best Practice Analysis

**Option A: Commit to Git**
Pros:
- Easy for anyone to run tests
- Consistent test data across developers

Cons:
- 20 MB in repo (not huge, but noticeable)
- Git history bloat if DB updated frequently
- May become stale over time

**Option B: Gitignore + Regenerate**
Pros:
- Smaller repo size
- Always fresh data (copy from production)

Cons:
- Need to run setup command before tests
- Test data may differ between developers

**Option C: Git LFS (Large File Storage)**
Pros:
- Keep in git but separate from main repo
- Version control for test data

Cons:
- Additional complexity (Git LFS setup)
- Most Git hosts charge for LFS storage

**Option D: Fixture Generation Script**
Pros:
- Small, crafted test data (few KB)
- Fast tests, precise control

Cons:
- Manual effort to create fixtures
- May not match real-world scenarios

### 4.2 Industry Practices

Research what similar projects do:
- Django projects (use fixtures or real DB copies?)
- Data pipeline projects
- Wiki bot/scraper projects

**Examples**: Find 3-5 real-world projects and document their approach.

### 4.3 Recommendation

**Recommended Approach**: [Pick one and justify]

**Justification**:
- Why this approach is best for Erenshor project
- How it fits with solo dev workflow
- Trade-offs accepted

**Implementation**:
```bash
# If not in git, provide command to generate test DB
make test-db
# or
erenshor test update-db
```

**Time Estimate**: 1 day

---

## Task 5: Performance Metrics Recommendations

**Priority**: LOW (Can defer to Phase 8)

**Assigned To**: AI (Claude)

**User Request**: Q3.14 - "Use SQL. Whatever metrics you think might be useful / interesting to have. What's actionable?"

**Context**: Want to track performance metrics in SQL. What metrics are worth tracking?

**Requirements**:
Recommend actionable, useful metrics to track.

**Deliverables**:

### 5.1 Metric Categories

**Extraction Performance**:
- Total extraction time (download + rip + export)
- Per-stage timing (download, rip, export)
- Database size
- Number of entities per type

**Upload Performance**:
- Wiki pages uploaded (count, time per page, failures)
- Sheets deployment time
- Image uploads (count, time, failures)

**Data Growth**:
- Entity counts over time (trend)
- Database size over time
- Number of wiki pages over time

**Error Tracking**:
- Extraction failures
- Upload failures
- Conflict count

### 5.2 Actionable Metrics

Focus on metrics that answer questions:

**Q: Is extraction getting slower?**
- A: Track extraction time per version

**Q: Which entity types are growing fastest?**
- A: Track entity counts per type over time

**Q: Are uploads getting slower?**
- A: Track upload time and pages per second

**Q: How often do conflicts occur?**
- A: Track conflict count per extraction

### 5.3 Recommended Schema

```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    variant TEXT NOT NULL,
    game_version TEXT,
    metric_type TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    metadata JSON
);

-- Examples of records
INSERT INTO metrics VALUES
    (1, 1697123456, 'main', '1.0.5.3', 'extraction', 'duration_seconds', 1234.5, '{"stage": "total"}'),
    (2, 1697123456, 'main', '1.0.5.3', 'extraction', 'duration_seconds', 45.2, '{"stage": "download"}'),
    (3, 1697123456, 'main', '1.0.5.3', 'entity_count', 'items', 2543, NULL),
    (4, 1697123456, 'main', '1.0.5.3', 'upload', 'pages_updated', 156, '{"output": "wiki"}');
```

### 5.4 Query Examples

Provide useful SQL queries:

```sql
-- Extraction time trend
SELECT game_version, metric_value
FROM metrics
WHERE metric_type = 'extraction' AND metric_name = 'duration_seconds'
ORDER BY timestamp;

-- Entity growth
SELECT timestamp, metric_name, metric_value
FROM metrics
WHERE metric_type = 'entity_count'
ORDER BY timestamp, metric_name;
```

**Time Estimate**: 1 day

---

## Task 6: Log Command UX Design

**Priority**: LOW (Can defer to backlog)

**Assigned To**: AI (Claude)

**User Request**: Q3.5, Q3.6 - "Any good suggestions here? What do you think will be the use case for the command? Do we need it?"

**Context**: User asks if `erenshor logs tail` and `erenshor logs show` commands are useful.

**Requirements**:
Analyze use cases and recommend UX.

**Deliverables**:

### 6.1 Use Case Analysis

**When would user use log commands?**

**Scenario 1**: Command failed, want to see what went wrong
```bash
$ erenshor extract
... (fails)

$ erenshor logs show --errors
# Shows recent errors from log
```

**Scenario 2**: Long-running operation, want to monitor progress
```bash
$ erenshor extract &
$ erenshor logs tail
# Live tail of log file
```

**Scenario 3**: Debugging, want to see full context around error
```bash
$ erenshor logs show --around-error
# Shows 20 lines before and after each error
```

### 6.2 Recommended Commands

**erenshor logs show**:
- Default: Last 50 lines or last 5 minutes (whichever is more)
- `--all`: Full log
- `--errors`: Only ERROR level messages
- `--warnings`: Only WARNING+ level messages
- `--since <time>`: Since timestamp (e.g., "5m ago", "1h ago")

**erenshor logs tail**:
- Live tail of log file (like `tail -f`)
- `--filter <pattern>`: Only show lines matching regex
- Ctrl+C to stop

**Alternative**: Skip these commands, user can use:
```bash
tail -f variants/main/logs/latest.log
grep ERROR variants/main/logs/latest.log
```

**Recommendation**: [Implement or skip? Justify.]

**Time Estimate**: 0.5 days

---

## Task 7: JSON Schema Type Sharing

**Priority**: LOW (Can defer to backlog)

**Assigned To**: AI (Claude)

**User Request**: Q3.12 - "How should we implement type sharing via JSON Schema? Any tooling support? Is it worth it?"

**Context**: AI suggested JSON Schema for sharing types between Python and TypeScript. User asks how to implement it.

**Requirements**:
Research tooling and provide concrete implementation approach.

**Deliverables**:

### 7.1 JSON Schema Approach

**Concept**: Define types once in JSON Schema, generate code for both languages.

**Example Schema** (`schemas/character.json`):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Character",
  "type": "object",
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "level": {"type": "integer"},
    "health": {"type": "integer"}
  },
  "required": ["id", "name"]
}
```

**Generated Python** (Pydantic):
```python
class Character(BaseModel):
    id: int
    name: str
    level: Optional[int] = None
    health: Optional[int] = None
```

**Generated TypeScript**:
```typescript
interface Character {
  id: number;
  name: string;
  level?: number;
  health?: number;
}
```

### 7.2 Tooling Options

**Option A: datamodel-code-generator (Python)**
- Generate Pydantic models from JSON Schema
- `pip install datamodel-code-generator`
- Command: `datamodel-codegen --input schema.json --output models.py`

**Option B: json-schema-to-typescript**
- Generate TypeScript types from JSON Schema
- `npm install -g json-schema-to-typescript`
- Command: `json2ts schema.json > types.ts`

**Option C: quicktype**
- Generate types for multiple languages from JSON Schema
- `npm install -g quicktype`
- Command: `quicktype -s schema schema.json -o models.py -l python`

### 7.3 Build Integration

**Where in build process?**
- Pre-commit hook (regenerate on schema changes)
- Manual command (`make generate-types`)
- CI/CD check (ensure generated code is up-to-date)

**Example Makefile**:
```makefile
generate-types:
    datamodel-codegen --input schemas/ --output src/erenshor/domain/entities/
    json2ts schemas/*.json --output src/maps/types/
```

### 7.4 Recommendation

**Is it worth it?**

**Pros**:
- Single source of truth for types
- Guaranteed consistency between Python and TypeScript
- Auto-completion and type checking

**Cons**:
- Additional build step complexity
- Another tool to maintain
- Schemas must be kept in sync with database

**Recommendation**: [Implement or skip? Justify.]

**Alternative**: Manually maintain types (simpler, more control, but risk of divergence).

**Time Estimate**: 1-2 days (research + setup)

---

## Summary

### Critical Blockers (must complete before Phase 1)
1. **Stable Entity IDs Analysis** - Requires user-provided database backups
2. **Managed Templates Inventory** - Review current implementation
3. **Cargo Integration Analysis** - User explicitly requested

### Important (should complete early)
4. **Test Database Best Practices** - Affects test setup in Phase 6

### Nice to Have (can defer to backlog)
5. **Performance Metrics Recommendations**
6. **Log Command UX Design**
7. **JSON Schema Type Sharing**

---

## Timeline

**Phase 0 Duration**: 1-2 weeks (assuming database backups provided promptly)

**Task Breakdown**:
- Task 1 (Stable IDs): 2-3 days (after backups provided)
- Task 2 (Templates): 1-2 days
- Task 3 (Cargo): 1-2 days
- Task 4 (Test DB): 1 day
- Task 5 (Metrics): 1 day
- Task 6 (Logs): 0.5 days
- Task 7 (JSON Schema): 1-2 days

**Total**: ~7-11 days of research work

---

## Deliverable Format

For each completed task, create a new document:
- `13.1-stable-entity-ids.md` - Stability analysis and recommendations
- `13.2-managed-templates.md` - Template inventory and structure
- `13.3-cargo-integration.md` - Cargo analysis and plan
- `13.4-test-database.md` - Best practice recommendation
- `13.5-performance-metrics.md` - Metrics recommendations
- `13.6-log-commands.md` - UX design (if implementing)
- `13.7-json-schema.md` - Type sharing approach (if implementing)

---

**End of Research Tasks**
