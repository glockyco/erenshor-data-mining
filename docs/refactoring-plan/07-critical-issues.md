# Critical Issues & Solutions

**Document Status**: Planning Phase - Requires User Decisions
**Date**: 2025-10-16
**Purpose**: Deep dives into critical issues raised in user feedback with concrete proposals

---

## Table of Contents

1. [Issue 1: Manual Content Preservation Without Markers](#1-manual-content-preservation-without-markers)
2. [Issue 2: Maps Performance with Full SQLite](#2-maps-performance-with-full-sqlite)
3. [Issue 3: Stable Entity IDs Across Game Versions](#3-stable-entity-ids-across-game-versions)
4. [Issue 4: Name Conflict Detection with ALL Wiki Pages](#4-name-conflict-detection-with-all-wiki-pages)
5. [Issue 5: Resume from Failure](#5-resume-from-failure)
6. [Issue 6: Change Detection for Game Updates](#6-change-detection-for-game-updates)
7. [Issue 7: TOML vs YAML Configuration](#7-toml-vs-yaml-configuration)
8. [Issue 8: CLI Documentation Generation](#8-cli-documentation-generation)
9. [Issue 9: Docker Feasibility](#9-docker-feasibility)
10. [Issue 10: Test Database Approach](#10-test-database-approach)

---

## 1. Manual Content Preservation Without Markers

### Problem Statement

From user feedback (section 4.5):
> "We MUST NOT introduce any special markers into wiki pages. We MUST use only the wiki normal wiki content. After all, this is a hobby project, and if a new hobby comes along, the remaining wiki team (who are NOT contributors / users of this project) must still be able to keep normal wiki maintenance / operations going as usual."

Original proposal used HTML comments like `<!-- AUTO-GENERATED -->` to mark boundaries. This is **not acceptable** because:
1. Wiki team must be able to maintain pages without our tooling
2. Special markers create dependency on our system
3. Manual edits would be lost if markers are removed

### Additional Context

From user feedback (section 1.3):
> "I've also had several situations where I updated a wiki page, found some issues, and wanted to re-update it again with the fixed content. Not easy to do currently."
>
> "there were pages that had some error in the content which I couldn't fix right away in the auto-updates, so I fixed the error manually in the wiki. However, with the next auto-update, the manually fixed wiki page would be overwritten with the incorrect content again (forcing me to manually update it again, etc.). Not sure how to best deal with such situations."

### Current Approach

We already have some page-type-specific logic that knows what sections to update. We need to formalize and extend this.

### Proposed Solution

**Option 1: Template-Based Detection (Recommended)**

Recognize standard MediaWiki templates and update only their parameters.

```python
def merge_page_content(original: str, generated: str) -> str:
    """Merge generated content into original, preserving manual sections."""

    # Parse original page
    original_tree = parse_wikitext(original)
    generated_tree = parse_wikitext(generated)

    # Find templates we manage (e.g., {{Item Infobox}}, {{Character Infobox}})
    managed_templates = ["Item Infobox", "Character Infobox", "Spell Infobox", ...]

    for template_name in managed_templates:
        original_template = original_tree.find_template(template_name)
        generated_template = generated_tree.find_template(template_name)

        if original_template and generated_template:
            # Replace template parameters with generated values
            original_template.parameters = generated_template.parameters

    # All other content (sections, text, etc.) is preserved
    return original_tree.to_wikitext()
```

**How It Works**:
1. We only update content inside templates we explicitly manage
2. Everything else (manual sections, notes, tips) is preserved
3. No special markers needed - relies on standard wiki syntax

**Limitations**:
- Only works for templated content
- Manual edits to template parameters will be overwritten
- Need to track which templates we manage

**Option 2: Section-Based Merge**

Update only specific sections by name.

```python
def merge_page_content(original: str, generated: str) -> str:
    """Merge by section names."""

    # Parse sections
    original_sections = parse_sections(original)
    generated_sections = parse_sections(generated)

    # Define which sections we manage
    managed_sections = {
        "Statistics",      # Auto-generated from DB
        "Loot Table",      # Auto-generated from DB
        "Spawn Locations", # Auto-generated from DB
    }

    # Merge sections
    for section_name in managed_sections:
        if section_name in generated_sections:
            original_sections[section_name] = generated_sections[section_name]

    # Preserve all other sections (Strategy, Tips, Trivia, etc.)
    return render_sections(original_sections)
```

**How It Works**:
1. Update only sections with known names
2. All other sections are preserved
3. Section names act as implicit "boundaries"

**Limitations**:
- Relies on consistent section naming
- If user renames section, we won't update it
- Need to track managed sections per entity type

**Option 3: Diff-Based Merge with Manual Review**

Generate diff, show to user, let them approve specific changes.

```python
def generate_update_preview(original: str, generated: str) -> DiffPreview:
    """Generate a preview of changes."""

    diff = compute_diff(original, generated)

    # Analyze diff to detect potential issues
    warnings = []
    if diff.has_deletions():
        warnings.append("Manual content will be deleted")
    if diff.modifies_non_template_content():
        warnings.append("Non-template content will change")

    return DiffPreview(diff, warnings)

# CLI usage
erenshor wiki push --review  # Show diffs, ask for confirmation per page
```

**How It Works**:
1. Generate full page from database
2. Compare with current wiki version
3. Show diff to user
4. User approves/rejects changes

**Limitations**:
- Manual approval for every update (tedious)
- Not suitable for automated updates
- Good for debugging/fixing errors though

### Recommendation

**Use Option 1 (Template-Based) as primary approach**, with Option 3 (Manual Review) available for special cases.

**Implementation Plan**:

1. **Define managed templates** in config:
```toml
[wiki.managed_templates]
item = ["Item Infobox", "Loot Table"]
character = ["Character Infobox", "Spawn Locations", "Abilities"]
spell = ["Spell Infobox", "Spell Ranks"]
```

2. **Parse and update only templates**:
```python
class TemplateManager:
    def update_page(self, original: str, generated: str, entity_type: str) -> str:
        managed_templates = config.wiki.managed_templates[entity_type]
        return merge_templates(original, generated, managed_templates)
```

3. **Handle manual fixes gracefully**:
```python
# If user manually fixed a bug in wiki, and we haven't fixed it in generator yet,
# provide --skip flag to skip specific pages

erenshor wiki push --skip "Sword"  # Skip this page for now
```

4. **Add review mode** for debugging:
```bash
erenshor wiki push --review  # Show diffs, ask per page
```

### Questions for User

1. **Which templates do we currently auto-generate**? Need complete list per entity type.
2. **Are there any sections (not templates) we need to update**? Or is everything in templates?
3. **How often do you manually fix bugs in wiki pages**? Should we prioritize fixing generators over allowing manual overrides?

---

## 2. Maps Performance with Full SQLite

### Problem Statement

From user feedback (section 6.3):
> "I guess there is some truth to the issues of full DB loading for maps. However, we want to extend the maps in the future to also offer search for items, characters, etc. so we can't really trim things down at all. All data will be needed in some form eventually. Any other solutions to deal with / avoid the long-ish loads?"

**Constraints**:
- Must use full SQLite database (not JSON)
- Need all data for future search functionality
- Current load times are slow

### Current Performance

**Estimated** (need to measure):
- Database size: ~20 MB (compressed)
- sql.js WASM load time: ~2 seconds
- Database parse time: ~1-3 seconds
- Total: ~5 seconds initial load

### Proposed Solutions

**Option 1: Progressive Loading with IndexedDB Caching**

Load database once, cache in browser storage.

```typescript
// On first visit: Load from network, cache in IndexedDB
async function loadDatabase(): Promise<SQL.Database> {
    // Check cache first
    const cached = await getFromIndexedDB('erenshor-db');
    if (cached && cached.version === CURRENT_VERSION) {
        return new SQL.Database(cached.data);
    }

    // Load from network
    const response = await fetch('/data/erenshor.sqlite');
    const buffer = await response.arrayBuffer();

    // Cache for next time
    await storeInIndexedDB('erenshor-db', {
        version: CURRENT_VERSION,
        data: buffer
    });

    return new SQL.Database(new Uint8Array(buffer));
}
```

**Benefits**:
- First load: ~5 seconds
- Subsequent loads: ~100ms (from cache)
- Cache automatically cleared when DB version changes

**Trade-offs**:
- Slightly more complex code
- Uses browser storage (~20 MB)
- Need cache invalidation strategy

**Option 2: Lazy Loading with Virtual Tables**

Load only map tiles data initially, lazy-load entity details on demand.

```typescript
// Initial load: Only map metadata
const mapMetadata = await loadMapMetadata(); // Small JSON file ~100 KB

// When user clicks on marker: Fetch full entity data
async function getEntityDetails(entityId: string) {
    // Query SQLite for this specific entity
    return db.exec(`SELECT * FROM entities WHERE id = ?`, [entityId]);
}
```

**Benefits**:
- Very fast initial load (~500ms)
- Minimal bandwidth usage
- Load data as needed

**Trade-offs**:
- Requires backend changes
- Can't do full-text search without full DB
- More complex data architecture

**Option 3: SQLite Compression + Streaming**

Compress database, stream decompression.

```typescript
import { gunzipSync } from 'fflate';

async function loadDatabase() {
    const response = await fetch('/data/erenshor.sqlite.gz');
    const compressed = await response.arrayBuffer();

    // Decompress (fast in WASM)
    const decompressed = gunzipSync(new Uint8Array(compressed));

    return new SQL.Database(decompressed);
}
```

**Benefits**:
- Smaller download size (~5 MB compressed)
- Faster network transfer
- Simple implementation

**Trade-offs**:
- Decompression time (~500ms)
- Slightly more complex build

**Option 4: Service Worker + Background Sync**

Use service worker to pre-cache database in background.

```typescript
// service-worker.ts
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('erenshor-v1').then((cache) => {
            // Pre-cache database
            return cache.add('/data/erenshor.sqlite');
        })
    );
});

// On page load: Database already cached by service worker
const cached = await caches.match('/data/erenshor.sqlite');
```

**Benefits**:
- After first visit, database always cached
- Works offline
- Standard browser API

**Trade-offs**:
- Service worker complexity
- Cache management
- Browser support (good but not perfect)

### Recommendation

**Combine Option 1 + Option 3**: Compression + IndexedDB caching.

**Implementation**:

1. **Compress database during build**:
```bash
gzip -9 erenshor.sqlite → erenshor.sqlite.gz
```

2. **Load with caching**:
```typescript
async function loadDatabase() {
    // Check IndexedDB cache
    const cached = await db.get('sqlite-db');
    if (cached?.version === DB_VERSION) {
        return new SQL.Database(cached.data);
    }

    // Load compressed from network
    const response = await fetch('/data/erenshor.sqlite.gz');
    const compressed = await response.arrayBuffer();
    const decompressed = gunzipSync(new Uint8Array(compressed));

    // Cache for next time
    await db.put('sqlite-db', {
        version: DB_VERSION,
        data: decompressed,
        timestamp: Date.now()
    });

    return new SQL.Database(decompressed);
}
```

3. **Show loading progress**:
```typescript
// Show progress during load
const progress = document.getElementById('loading-progress');

const response = await fetch('/data/erenshor.sqlite.gz');
const reader = response.body.getReader();
const contentLength = response.headers.get('content-length');

let receivedLength = 0;
const chunks = [];

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    chunks.push(value);
    receivedLength += value.length;

    // Update progress bar
    progress.value = (receivedLength / contentLength) * 100;
}
```

**Expected Performance**:
- First load: ~3 seconds (5 MB download + decompression)
- Subsequent loads: ~100ms (IndexedDB cache)
- Compression ratio: ~70% (20 MB → 6 MB)

**Future Enhancement**: Service worker for offline support.

### Questions for User

1. **What is actual current database size**? Need to measure to verify estimates.
2. **What is acceptable load time**? <1s? <3s? <5s?
3. **Should we prioritize offline support** (service worker)?

---

## 3. Stable Entity IDs Across Game Versions

### Problem Statement

From user feedback (section 5.2, 5.5):
> "Yeah, brittle stable keys are a big issue. We have some ID columns for some types of entities (for example Spells have IDs even in the game files, but we already observed cases of duplicate IDs, so those cannot be fully trusted unfortunately). It's really a hard problem. If, e.g., a name changes, we want to RENAME the wiki page so we don't lose any manually added content, but how do we make sure we know which new page belongs to which old one?"
>
> "The main questions is just: which DB information IS stable across game versions? I'm honestly not totally sure. Perhaps you can check this and make some suggestions?"

**Core Challenge**: Need stable identifiers to track entities across game versions, but:
- Names can change (renames)
- In-game IDs sometimes duplicate
- Database IDs regenerated every export
- No guaranteed stable identifier

### Investigation Needed

Before proposing solutions, need to analyze what data IS stable. This requires comparing databases across game versions.

**Analysis Plan**:

1. **Compare character exports across versions**
2. **Compare item exports across versions**
3. **Compare spell exports across versions**
4. **Identify what changes and what stays constant**

### Potential Stable Identifiers (Hypotheses)

Need to verify these by examining actual data:

**Hypothesis 1: Unity Resource Names**

Unity asset names (e.g., `prefab://Characters/GoblinWarrior`) might be stable.

**Test**: Check if resource names stay constant across game versions.

```python
def analyze_resource_name_stability(old_db: Path, new_db: Path):
    """Check if Unity resource names are stable."""

    old_chars = query_characters(old_db)
    new_chars = query_characters(new_db)

    # Group by resource name
    old_by_resource = {c.resource_name: c for c in old_chars}
    new_by_resource = {c.resource_name: c for c in new_chars}

    # Check for matches
    matches = 0
    renames = []

    for resource_name, old_char in old_by_resource.items():
        if resource_name in new_by_resource:
            new_char = new_by_resource[resource_name]
            matches += 1

            if old_char.name != new_char.name:
                renames.append((resource_name, old_char.name, new_char.name))

    print(f"Matched by resource name: {matches}/{len(old_chars)}")
    print(f"Detected renames: {len(renames)}")
    for resource, old_name, new_name in renames:
        print(f"  {resource}: '{old_name}' → '{new_name}'")
```

**Hypothesis 2: Composite Keys**

Combination of attributes might uniquely identify entities.

For characters: `(type, level, base_health, base_damage)`
For items: `(slot, required_level, base_stats_hash)`
For spells: `(name_prefix, mana_cost, effect_type)`

**Test**: Check collision rate for composite keys.

**Hypothesis 3: Content Hash**

Hash of essential properties (excluding things like descriptions that might change).

```python
def compute_entity_fingerprint(entity) -> str:
    """Compute stable hash of essential properties."""

    # For character: type + level + base stats
    if isinstance(entity, Character):
        content = f"{entity.type}|{entity.level}|{entity.health}|{entity.damage}"

    # For item: slot + required level + base stats
    elif isinstance(entity, Item):
        content = f"{entity.slot}|{entity.required_level}|{entity.stats_hash}"

    # etc.

    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

**Test**: Check if fingerprints are unique and stable across versions.

### Proposed Solution (After Investigation)

**Step 1: Investigate Stability**

Need to run analysis on existing database backups to determine what's stable.

```bash
# User action required: Provide 2-3 database backups from different game versions
erenshor analyze stability \
    --old backups/erenshor-main-v1.0.5.0.sqlite \
    --new backups/erenshor-main-v1.0.5.3.sqlite \
    --output stability-report.json
```

**Output**:
```json
{
    "characters": {
        "total_old": 350,
        "total_new": 365,
        "matched_by_resource_name": 340,
        "matched_by_composite_key": 358,
        "matched_by_fingerprint": 355,
        "unmatched": 7,
        "renames_detected": 5,
        "new_entities": 15
    },
    "items": { ... },
    "spells": { ... }
}
```

**Step 2: Choose Best Strategy Based on Data**

Once we know what's stable, implement the most reliable approach.

**Option A: Resource Name (if stable)**
```python
entity_uid = f"{entity_type}/{resource_name}"
```

**Option B: Composite Key (if reliable)**
```python
entity_uid = f"{entity_type}/{composite_key}"
```

**Option C: Fingerprint (if unique)**
```python
entity_uid = f"{entity_type}/{content_fingerprint}"
```

**Option D: Hybrid (most robust)**
```python
def compute_entity_uid(entity) -> str:
    # Try resource name first
    if entity.resource_name:
        return f"{entity.type}/resource/{entity.resource_name}"

    # Fall back to fingerprint
    fingerprint = compute_fingerprint(entity)
    return f"{entity.type}/fingerprint/{fingerprint}"
```

**Step 3: Handle Edge Cases**

For entities that can't be matched:
1. Mark as "new entity" (create new wiki page)
2. Mark as "deleted entity" (don't update page, keep for reference)
3. Flag for manual review if uncertain

**Step 4: Migration Helper**

Provide tool to help match old registry to new entities:

```bash
erenshor registry migrate \
    --old-db backups/old.sqlite \
    --new-db current.sqlite \
    --old-registry registry-old.json \
    --output registry-new.json
```

### Recommendation

**Cannot recommend specific solution until investigation is done.**

**User Action Required**:
1. Provide 2-3 database backups from different game versions
2. Run stability analysis
3. Review results
4. Choose stable identifier strategy based on data

**Implementation**: Defer to after investigation phase.

---

## 4. Name Conflict Detection with ALL Wiki Pages

### Problem Statement

From user feedback (section 4.6):
> "we need some way to track ALL conflicts, not just the ones for which we have entities. As mentioned somewhere above, this MUST also include random manually-created pages that have no association with our automated wiki update system at all. From a UX perspective, how to best notify the project user (i.e., me) of any conflicts that need to be resolved? The current system is quite inadequate in this regard - you always have to manually check via commands whether there are any conflicts, and the conflict detection does not consider pages that aren't fully implemented entities."

**Requirements**:
1. Track ALL wiki pages (managed and unmanaged)
2. Detect conflicts between new entities and existing pages
3. Notify user proactively when conflicts exist
4. Make conflicts visible without having to run special commands

### Proposed Solution

**Architecture**:

```
┌─────────────────────────────────────────────────────┐
│              Wiki Pages (All)                       │
│                                                     │
│  • Managed Entity Pages (Items, Characters, etc.)  │
│  • Manual Pages (Guides, Lore, etc.)              │
│  • System Pages (Categories, Templates)            │
└───────────────────────┬─────────────────────────────┘
                        │
                        ↓
         ┌──────────────────────────────┐
         │  Registry SQLite Database    │
         │                              │
         │  Table: all_wiki_pages       │
         │  - title (PRIMARY KEY)       │
         │  - is_managed (BOOLEAN)      │
         │  - last_seen (TIMESTAMP)     │
         │  - page_type (entity|manual) │
         └──────────────────────────────┘
                        │
                        ↓
         ┌──────────────────────────────┐
         │   Conflict Detection         │
         │                              │
         │  • New entity name           │
         │  • Check all_wiki_pages      │
         │  • Flag if exists            │
         └──────────────────────────────┘
```

**Implementation**:

**1. Track All Wiki Pages During Fetch**

```python
def fetch_all_wiki_pages(api: WikiAPIClient, registry: Registry):
    """Fetch and register ALL wiki pages."""

    # Get all pages in main namespace
    all_pages = api.list_all_pages(namespace=0)

    for page in all_pages:
        # Determine if page is managed by us
        is_managed = page.title in registry.get_managed_page_titles()

        # Store in registry
        registry.register_wiki_page(
            title=page.title,
            is_managed=is_managed,
            last_seen=datetime.now()
        )
```

**2. Check Conflicts Before Creating Pages**

```python
def detect_conflicts(entity: Entity, registry: Registry) -> list[Conflict]:
    """Check if entity name conflicts with existing pages."""

    proposed_title = entity.name  # Or with disambiguation suffix

    # Check if page exists
    existing_page = registry.get_wiki_page(proposed_title)

    if existing_page:
        if existing_page.is_managed:
            # Conflict with another managed entity
            return [Conflict(
                type=ConflictType.MANAGED_ENTITY,
                entity=entity,
                existing_page=existing_page,
                resolution="Need disambiguation"
            )]
        else:
            # Conflict with manual page
            return [Conflict(
                type=ConflictType.MANUAL_PAGE,
                entity=entity,
                existing_page=existing_page,
                resolution="Must rename entity or manual page"
            )]

    return []  # No conflict
```

**3. Proactive Conflict Reporting**

Show conflicts automatically at end of every relevant command:

```python
# After extract
def post_extract_report(registry: Registry):
    conflicts = registry.detect_all_conflicts()

    if conflicts:
        console.print("\n[yellow]⚠ Name Conflicts Detected[/yellow]\n")
        for conflict in conflicts:
            console.print(f"  • {conflict.entity.name}")
            console.print(f"    Conflicts with: {conflict.existing_page.title}")
            console.print(f"    Resolution: {conflict.resolution}\n")

        console.print("Run [cyan]erenshor wiki conflicts[/cyan] for details")
```

**4. Dedicated Conflict Management Command**

```bash
# View all conflicts
erenshor wiki conflicts

# Output:
# Name Conflicts (3)
#
# 1. Item "Sword"
#    Conflicts with: Manual page "Sword" (https://erenshor.wiki.gg/wiki/Sword)
#    Suggested resolution: Rename to "Sword (item)"
#    Action: erenshor wiki resolve-conflict 1 --strategy suffix
#
# 2. Character "Goblin"
#    Conflicts with: Managed entity (existing item)
#    Suggested resolution: Use disambiguation
#    Action: erenshor wiki resolve-conflict 2 --strategy manual
#
# 3. Spell "Shield"
#    Conflicts with: Manual page "Shield" (guide)
#    Suggested resolution: Keep manual page, rename entity
#    Action: erenshor wiki resolve-conflict 3 --strategy manual
```

**5. Conflict Resolution Workflow**

```bash
# Interactive resolution
erenshor wiki resolve-conflict 1

# Prompts:
# Conflict: Item "Sword" vs Manual page "Sword"
#
# Options:
#   1. Rename entity to "Sword (item)" [recommended]
#   2. Create multi-entity page (merge)
#   3. Manual mapping (specify custom title)
#   4. Skip (don't create page for this entity)
#
# Choose option [1-4]:
```

**6. Conflict Summary in Status**

```bash
erenshor status

# Output includes:
# Wiki Status:
#   Managed pages: 850
#   Manual pages: 245
#   Conflicts: 3 (run 'erenshor wiki conflicts' for details)
#   Pages needing update: 15
```

### Database Schema

```sql
-- Track ALL wiki pages
CREATE TABLE all_wiki_pages (
    title TEXT PRIMARY KEY,
    is_managed BOOLEAN NOT NULL,
    last_seen INTEGER NOT NULL,  -- Unix timestamp
    page_type TEXT,  -- 'entity', 'guide', 'category', 'template', etc.
    wiki_url TEXT
);

-- Track conflicts
CREATE TABLE conflicts (
    id INTEGER PRIMARY KEY,
    entity_uid TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    conflicting_page_title TEXT NOT NULL,
    conflict_type TEXT NOT NULL,  -- 'managed', 'manual'
    detected_at INTEGER NOT NULL,
    resolved BOOLEAN DEFAULT 0,
    resolution_strategy TEXT,  -- 'suffix', 'manual', 'skip', etc.
    FOREIGN KEY (conflicting_page_title) REFERENCES all_wiki_pages(title)
);

-- Index for fast lookups
CREATE INDEX idx_conflicts_unresolved ON conflicts(resolved) WHERE resolved = 0;
```

### User Experience Flow

**1. After Extract**:
```
✓ Extraction complete!

Database: variants/main/erenshor-main.sqlite
Entities: 2,500 items, 350 characters, 180 spells

⚠ 3 name conflicts detected!
  • Item "Sword" conflicts with manual page
  • Character "Goblin" conflicts with existing item
  • Spell "Shield" conflicts with manual page

Run 'erenshor wiki conflicts' to review and resolve.
```

**2. View Conflicts**:
```bash
$ erenshor wiki conflicts

Name Conflicts (3 unresolved)

1. Item "Sword"
   Conflicts with: https://erenshor.wiki.gg/wiki/Sword (manual page)
   Detected: 2025-10-16 10:30
   Suggested: Rename to "Sword (item)"

2. Character "Goblin"
   Conflicts with: https://erenshor.wiki.gg/wiki/Goblin (Item)
   Detected: 2025-10-16 10:30
   Suggested: Use disambiguation

3. Spell "Shield"
   Conflicts with: https://erenshor.wiki.gg/wiki/Shield (manual guide)
   Detected: 2025-10-16 10:30
   Suggested: Keep manual page, rename entity to "Shield (spell)"

Resolve with: erenshor wiki resolve-conflict <id>
```

**3. Resolve**:
```bash
$ erenshor wiki resolve-conflict 1 --strategy suffix

✓ Conflict resolved!
  Entity: Item "Sword"
  Resolution: Will create page "Sword (item)"
  Added manual mapping: item/sword_001 → "Sword (item)"

2 conflicts remaining.
```

**4. Automatic Detection on Wiki Fetch**:

Every time we fetch wiki pages, update `all_wiki_pages` table and re-check conflicts.

```bash
$ erenshor wiki fetch

Fetching wiki pages...
━━━━━━━━━━━━━━━━━━━━━━ 100% (1,095 pages)

✓ Fetch complete!
  Managed pages: 850
  Manual pages: 245
  New pages: 12

⚠ 1 new conflict detected!
  • New item "Magic Sword" conflicts with existing manual page

Run 'erenshor wiki conflicts' to review.
```

### Recommendation

Implement full conflict detection system with:
1. Track ALL wiki pages (managed + manual)
2. Proactive conflict detection and reporting
3. Dedicated conflict management UI
4. Automatic alerts in command outputs
5. Interactive resolution workflow

### Questions for User

1. **Should we scan for conflicts on every command**, or only on `extract` and `wiki fetch`?
2. **What conflict resolution strategies should be available**? (suffix, prefix, manual, skip, multi-entity)
3. **Should we auto-resolve simple conflicts** (e.g., when there's only one entity with that name)?

---

## 5. Resume from Failure

### Problem Statement

From user feedback (section 2.5):
> "Resume from failure sure would be a nice feature to have. For example, I'd like to avoid having to re-run AssetRipper just because the sheets upload failed for some reason. Of course, I could just manually execute the sheets command instead of the triggering the full pipeline again, but that's somewhat tedious, especially if the failure is in an earlier stage and I then have to run multiple commands after each other to fully finish the pipeline. Not sure how tricky it is to implement such a 'resume from failure' system though?"

**Goal**: If pipeline fails partway through, be able to resume without re-running completed stages.

**Example Scenario**:
```
erenshor update  # Full pipeline
  ✓ Download game files (10 minutes)
  ✓ Extract Unity project (15 minutes)
  ✓ Export to database (5 minutes)
  ✗ Wiki push failed (API error)

# Want to resume without re-downloading/extracting
erenshor update --resume  # Skip completed stages, retry from wiki push
```

### Proposed Solution

**Option 1: State Tracking with Checkpoints**

Track pipeline progress in state file.

```python
@dataclass
class PipelineState:
    variant: str
    started_at: datetime
    last_updated: datetime
    completed_stages: list[str]
    failed_stage: str | None
    error: str | None

# State file: .erenshor/pipeline-state.json
{
    "variant": "main",
    "started_at": "2025-10-16T10:00:00Z",
    "last_updated": "2025-10-16T10:35:00Z",
    "completed_stages": ["download", "extract", "export"],
    "failed_stage": "wiki_push",
    "error": "API rate limit exceeded"
}
```

**Implementation**:

```python
def run_pipeline(variant: str, resume: bool = False):
    """Run full pipeline with resume support."""

    stages = [
        ("download", download_game),
        ("extract", extract_unity_project),
        ("export", export_to_database),
        ("wiki_update", update_wiki),
        ("sheets_deploy", deploy_sheets),
        ("maps_export", export_maps),
    ]

    # Load state if resuming
    state = PipelineState.load() if resume else PipelineState.new(variant)

    for stage_name, stage_func in stages:
        # Skip if already completed
        if stage_name in state.completed_stages:
            console.print(f"[green]✓[/green] {stage_name} (already completed)")
            continue

        try:
            console.print(f"[cyan]Running {stage_name}...[/cyan]")
            stage_func(variant)
            state.mark_completed(stage_name)
            state.save()
        except Exception as e:
            state.mark_failed(stage_name, str(e))
            state.save()
            raise

    # Clear state on full success
    state.clear()
```

**CLI Usage**:

```bash
# Run full pipeline
erenshor update

# If fails, resume from last successful stage
erenshor update --resume

# Or manually run remaining stages
erenshor wiki push
erenshor sheets deploy
```

**Option 2: Idempotent Stages with Skip Detection**

Make each stage idempotent and auto-detect if it needs to run.

```python
def download_game(variant: str):
    """Download game files (idempotent)."""

    game_dir = paths.game_files

    # Check if already downloaded
    if game_dir.exists() and is_up_to_date(game_dir):
        console.print("[green]✓[/green] Game files already downloaded")
        return

    # Download if needed
    steamcmd.download(variant)
```

**Benefits**:
- No explicit state tracking needed
- Each stage checks if work is needed
- Naturally handles resume

**Trade-offs**:
- Need reliable "is work needed?" checks
- Some stages hard to make idempotent
- Might re-do work unnecessarily

**Option 3: Explicit Stage Commands (Manual Resume)**

No automatic resume, user manually runs remaining stages.

```bash
# Pipeline fails at wiki push
erenshor update
  ✓ download
  ✓ extract
  ✓ export
  ✗ wiki push (failed)

# User manually continues
erenshor wiki push    # Retry
erenshor sheets deploy
erenshor maps export
```

**Benefits**:
- Simple, no magic
- User has full control
- No state tracking needed

**Trade-offs**:
- Manual effort
- User must remember what's left

### Recommendation

**Combination of Option 1 + Option 3**: State tracking with manual control.

**Implementation**:

1. **Track state automatically** (no user action needed):
```python
# Every stage completion is recorded
state.mark_completed("export")
state.save()
```

2. **Show resume hint on failure**:
```bash
$ erenshor update

✓ Download (10m 30s)
✓ Extract (15m 15s)
✓ Export (5m 10s)
✗ Wiki push failed: API rate limit exceeded

Pipeline failed at: wiki_push
Already completed: download, extract, export

To resume:
  erenshor update --resume    # Automatically skip completed stages

Or manually:
  erenshor wiki push          # Retry failed stage
  erenshor sheets deploy      # Continue with remaining stages
```

3. **Resume flag**:
```bash
$ erenshor update --resume

Pipeline state found (failed at wiki_push)

[green]✓[/green] download (skipped - already completed)
[green]✓[/green] extract (skipped - already completed)
[green]✓[/green] export (skipped - already completed)
[cyan]⟳[/cyan] wiki push (retrying...)
```

4. **Clear state on success**:
```python
# After full pipeline completes
state.clear()  # Remove state file
```

5. **Status command shows state**:
```bash
$ erenshor status

Pipeline Status:
  State: Failed (wiki_push)
  Started: 2025-10-16 10:00:00
  Last stage: export (completed)
  Failed stage: wiki_push
  Error: API rate limit exceeded

Resume with: erenshor update --resume
```

### Edge Cases

**What if user manually runs stages?**

State tracking handles this:
```python
# User ran wiki push manually after failure
state.mark_completed("wiki_push")

# Now resume skips to next stage
erenshor update --resume  # Starts at sheets_deploy
```

**What if database changes between resume?**

Detect and warn:
```python
def run_pipeline(variant: str, resume: bool = False):
    if resume:
        state = PipelineState.load()

        # Check if database changed since failure
        db_hash = compute_hash(paths.database)
        if db_hash != state.database_hash:
            console.print("[yellow]⚠ Warning: Database changed since pipeline failed[/yellow]")
            console.print("Previous stages used different data. Consider re-running full pipeline.")

            if not Confirm.ask("Continue anyway?"):
                return
```

**What if resume is stale (old failure)?**

Add timeout:
```python
# State older than 24 hours? Ignore and start fresh
if state.age > timedelta(hours=24):
    console.print("[yellow]Pipeline state is stale (> 24 hours old)[/yellow]")
    console.print("Starting fresh pipeline...")
    state.clear()
    resume = False
```

### Questions for User

1. **What is acceptable state timeout?** 24 hours? 48 hours? Never?
2. **Should resume be default behavior** or require explicit flag?
3. **Should we support resuming individual output stages** (wiki/sheets/maps) or only full pipeline?

---

## 6. Change Detection for Game Updates

### Problem Statement

From user feedback (section 11):
> "New mechanics CAN be visible in ScriptableObjects, but often also come from completely new C# scripts."
>
> "Not sure what you mean by 'schema changes'. The game does NOT have a DB. We DO have one, of course, but we know about any changes to DB anyway because we're the ones who need to implement them...."
>
> "Should probably discuss this a bit more to figure out what are actionable insights that actually help (wiki) maintenance and what's just random noise that doesn't really help anyone."

**Clarification Needed**: The "schema changes" referred to changes in OUR database schema (not the game's). When game introduces new mechanics, we need to:
1. Detect it (new fields, new entity types)
2. Update C# listeners to export it
3. Update wiki templates to display it

**Real Questions**:
1. How to detect new game mechanics that need manual intervention?
2. What changes are actionable vs. just noise?
3. How to surface this information effectively?

### Types of Changes

**Type 1: Data Changes (Automatic)**
- New entities (items, characters, spells)
- Removed entities
- Renamed entities
- Modified stats

These are automatically handled by our export system.

**Type 2: Mechanic Changes (Manual Intervention Required)**
- New fields in ScriptableObjects (e.g., "CraftingTime" added to items)
- New entity types (e.g., "Achievements" added to game)
- New C# scripts with game data (e.g., new quest system)

These require us to:
1. Update C# listener to export new field
2. Update database schema
3. Update wiki templates

**Type 3: Game Content Changes (Low Priority)**
- Bug fixes
- Balance changes
- UI changes

These don't need our attention.

### Proposed Detection System

**Goal**: Detect Type 2 changes (mechanics) and surface them for manual review.

**Detection Methods**:

**Method 1: C# Script Diff**

Compare Unity project C# scripts across versions.

```bash
# After AssetRipper extraction
erenshor changes detect-scripts \
    --old backups/unity-v1.0.5.0/ \
    --new variants/main/unity/ \
    --output script-changes.json
```

**Output**:
```json
{
    "new_scripts": [
        "Assets/Scripts/CraftingSystem.cs",
        "Assets/Scripts/AchievementManager.cs"
    ],
    "modified_scripts": [
        {
            "path": "Assets/Scripts/Item.cs",
            "changes": [
                "Added field: float craftingTime",
                "Added method: CanCraft()"
            ]
        }
    ],
    "removed_scripts": []
}
```

**Implementation**:
```python
def detect_script_changes(old_unity_dir: Path, new_unity_dir: Path) -> ScriptChanges:
    """Detect C# script changes."""

    old_scripts = scan_csharp_files(old_unity_dir)
    new_scripts = scan_csharp_files(new_unity_dir)

    # New scripts
    new_files = [s for s in new_scripts if s not in old_scripts]

    # Modified scripts
    modified = []
    for script_path in old_scripts:
        if script_path in new_scripts:
            old_content = (old_unity_dir / script_path).read_text()
            new_content = (new_unity_dir / script_path).read_text()

            if old_content != new_content:
                # Parse AST to detect specific changes
                changes = analyze_csharp_diff(old_content, new_content)
                modified.append({
                    "path": script_path,
                    "changes": changes
                })

    return ScriptChanges(new_files, modified, ...)
```

**Method 2: ScriptableObject Field Comparison**

Compare fields in exported ScriptableObjects.

```python
def detect_new_fields(old_db: Path, new_db: Path) -> list[NewField]:
    """Detect new fields in ScriptableObjects."""

    # Get table schemas
    old_schema = get_schema(old_db)
    new_schema = get_schema(new_db)

    new_fields = []

    for table_name in new_schema:
        if table_name in old_schema:
            old_cols = set(old_schema[table_name].columns)
            new_cols = set(new_schema[table_name].columns)

            added_cols = new_cols - old_cols

            for col in added_cols:
                new_fields.append(NewField(
                    table=table_name,
                    column=col,
                    type=new_schema[table_name].column_types[col]
                ))

    return new_fields
```

**Output**:
```
New Fields Detected:

Table: Items
  • craftingTime (REAL) - New field in Items table
    Action: Update ItemListener.cs to export this field
    Action: Update Item wiki template to display crafting time

Table: Characters
  • factionId (INTEGER) - New field in Characters table
    Action: Update CharacterListener.cs to export this field
    Action: Update Character wiki template to display faction
```

**Method 3: ScriptableObject Type Discovery**

Detect completely new ScriptableObject types.

```python
def discover_scriptableobject_types(unity_dir: Path) -> list[str]:
    """Find all ScriptableObject types in Unity project."""

    # Scan for classes inheriting ScriptableObject
    scriptable_objects = []

    for script_file in find_csharp_files(unity_dir):
        if inherits_from(script_file, "ScriptableObject"):
            class_name = get_class_name(script_file)
            scriptable_objects.append(class_name)

    return scriptable_objects

# Compare across versions
old_types = discover_scriptableobject_types(old_unity_dir)
new_types = discover_scriptableobject_types(new_unity_dir)

newly_added = set(new_types) - set(old_types)
```

**Output**:
```
New ScriptableObject Types:

• AchievementData
  Location: Assets/Scripts/AchievementData.cs
  Action: Create AchievementListener.cs to export to database
  Action: Create Achievement wiki template

• CraftingRecipe
  Location: Assets/Scripts/CraftingRecipe.cs
  Action: Create CraftingRecipeListener.cs to export to database
  Action: Create CraftingRecipe wiki template
```

### Actionable Change Report

Combine all detection methods into single actionable report:

```bash
$ erenshor changes detect

Detecting changes between v1.0.5.0 and v1.0.5.3...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Game Update Summary (v1.0.5.0 → v1.0.5.3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Data Changes (Automatic):
  • 5 new items
  • 2 new characters
  • 1 renamed: "Sword" → "Iron Sword"
  • 3 stat changes

✅ No action required - exported automatically

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Mechanic Changes (Manual Intervention Required):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. New Field: Items.craftingTime
   Type: REAL (float)
   Detected in: 450 items have non-null values

   Actions:
   • Update ItemListener.cs to export craftingTime
   • Update Item wiki template to display crafting time
   • Update Google Sheets query to include craftingTime

2. New ScriptableObject Type: AchievementData
   Location: Assets/Scripts/AchievementData.cs
   Count: 25 achievements found

   Actions:
   • Create AchievementListener.cs
   • Create Achievements table in database
   • Create Achievement wiki template
   • Add achievements to Google Sheets

3. Modified Script: CharacterData.cs
   Changes:
   • Added field: int factionId
   • Added field: FactionType faction

   Actions:
   • Update CharacterListener.cs to export faction data
   • Update Character wiki template to display faction
   • Consider creating Faction entity type

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Action Items:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Priority 1 (New Features):
  [ ] Implement Achievement export
  [ ] Implement Faction tracking

Priority 2 (Field Additions):
  [ ] Export Items.craftingTime
  [ ] Export Characters.factionId

Priority 3 (Wiki Templates):
  [ ] Update Item template for crafting time
  [ ] Create Achievement template
  [ ] Update Character template for faction

Full report: variants/main/logs/changes-v1.0.5.0-to-v1.0.5.3.json
```

### Integration with Workflow

**After Export**:

```bash
$ erenshor extract

✓ Extraction complete!

⚠️ New game mechanics detected!
  • 1 new ScriptableObject type (AchievementData)
  • 1 new field (Items.craftingTime)

Run 'erenshor changes detect' for details and action items.
```

**Persistence**:

Track detected changes until acknowledged:

```bash
# View changes
erenshor changes show

# Acknowledge (mark as reviewed)
erenshor changes ack

# Or acknowledge specific item
erenshor changes ack --item "Items.craftingTime"
```

### Recommendation

Implement change detection with focus on **actionable insights**:

1. **Detect new fields in existing tables** → Need to update listener + wiki template
2. **Detect new ScriptableObject types** → Need to create listener + wiki template
3. **Show clear action items** → What code needs to be written
4. **Persist until acknowledged** → Don't lose track of required work

### Questions for User

1. **What level of detail is helpful** in change reports? Too much noise vs. too little?
2. **Should we attempt to auto-generate listener code** for new fields/types?
3. **How to handle changes that require decisions** (e.g., should faction be separate entity or just a field)?

---

## 7. TOML vs YAML Configuration

### Problem Statement

From user feedback (section 3.3):
> "TOML is fine I guess? Just curious about your justification to pick it over YAML? For example, 'Significant whitespace' is something that Python itself also has, and 'parsing inconsistencies' seems like quite a vague claim? Compared to TOML's 'flat' structure, YAML's indentations might actually make it easire to a big-picture overview of 'nested' settings / hierarchies."
>
> "What would we need to switch to YAML? Would it be 'worth it'?"

Decision already made to stick with TOML, but user asked for justification. Let's provide detailed comparison.

### Detailed Comparison

**TOML**:

```toml
[paths]
repo_root = "."
variants_dir = "variants"

[outputs.wiki]
api_url = "https://erenshor.wiki.gg/api.php"
base_url = "https://erenshor.wiki.gg/wiki/"
bot_username = ""
bot_password = ""

[outputs.wiki.rate_limiting]
batch_size = 25
delay = 1.0

[variants.main]
enabled = true
app_id = "2382520"
database = "main/erenshor-main.sqlite"
```

**YAML Equivalent**:

```yaml
paths:
  repo_root: .
  variants_dir: variants

outputs:
  wiki:
    api_url: https://erenshor.wiki.gg/api.php
    base_url: https://erenshor.wiki.gg/wiki/
    bot_username: ""
    bot_password: ""
    rate_limiting:
      batch_size: 25
      delay: 1.0

variants:
  main:
    enabled: true
    app_id: "2382520"
    database: main/erenshor-main.sqlite
```

### Pros and Cons

| Aspect | TOML | YAML |
|--------|------|------|
| **Readability** | Clean, explicit sections | More compact, visual hierarchy |
| **Nesting** | Verbose for deep nesting | Natural indentation |
| **Whitespace** | Not significant | Significant (can cause errors) |
| **Quoting** | Strings can be unquoted | Strings can be unquoted |
| **Comments** | `#` comments | `#` comments |
| **Multi-line** | `"""` for multiline strings | `\|` or `>` for multiline |
| **Types** | Strong typing (int, float, bool, date) | Weak typing (everything can be string) |
| **Complexity** | Simple spec, easy to implement | Complex spec, many edge cases |
| **Parsing** | Consistent across implementations | Inconsistent (YAML 1.1 vs 1.2, etc.) |

### Language Support

**TOML**:
- Python: ✅ Native (`tomllib` in 3.11+)
- C#: ✅ Tomlyn library (well-maintained)
- TypeScript: ✅ smol-toml (small, fast)

**YAML**:
- Python: ✅ PyYAML (standard)
- C#: ✅ YamlDotNet (well-maintained)
- TypeScript: ✅ js-yaml (standard)

Both have good support in all three languages we use.

### The "Parsing Inconsistencies" Claim

**YAML Issues**:

1. **Multiple versions** (YAML 1.1 vs 1.2 with breaking changes)
2. **Type coercion surprises**:
   ```yaml
   # These are all interpreted as booleans in YAML 1.1:
   answer: no     # false
   answer: yes    # true
   answer: on     # true
   answer: off    # false

   # But these are strings:
   answer: "no"   # "no"

   # Norway problem:
   country: NO    # false (interpreted as boolean!)
   country: "NO"  # "NO" (correct)
   ```

3. **Indentation errors** hard to debug:
   ```yaml
   # This is valid:
   foo:
     bar: 1
     baz: 2

   # This looks valid but is wrong (mixing spaces/tabs):
   foo:
   	bar: 1   # Tab here
     baz: 2   # Spaces here
   ```

4. **Anchor/alias complexity**:
   ```yaml
   defaults: &defaults
     timeout: 30
     retries: 3

   api:
     <<: *defaults
     url: https://example.com
   ```

**TOML doesn't have these issues** - what you see is what you get.

### TOML "Flat" Structure Issue

User mentioned TOML's "flat" structure vs YAML's hierarchy. Let's address this:

**TOML IS hierarchical**, just uses different syntax:

```toml
# Explicit section headers (more verbose but clearer)
[outputs.wiki.rate_limiting]
batch_size = 25
delay = 1.0

[outputs.sheets.rate_limiting]
batch_size = 1000
delay = 5.0
```

vs

```yaml
# Implicit hierarchy via indentation (more compact)
outputs:
  wiki:
    rate_limiting:
      batch_size: 25
      delay: 1.0
  sheets:
    rate_limiting:
      batch_size: 1000
      delay: 5.0
```

**For our config size** (small to medium), both are fine. YAML would be slightly more compact, but not dramatically.

### Switching Cost

**To switch from TOML to YAML**:

1. Convert `config.toml` → `config.yaml` (trivial)
2. Update Python config loading (change library)
3. Update C# config loading (change library)
4. Update TypeScript config loading (change library)
5. Update documentation

**Estimated effort**: ~2-4 hours

**Worth it?** Probably not, given:
- TOML is working fine
- User said "TOML is fine I guess" and "I think TOML looks 'cleaner'"
- Switching provides minimal benefit
- Would delay actual refactoring work

### Recommendation

**Stick with TOML** for these reasons:

1. **Already decided** - User accepted it as "fine"
2. **Cleaner** - User's own words
3. **Simpler spec** - Fewer gotchas
4. **Better typing** - Explicit types reduce errors
5. **No Norway problem** - Less surprising behavior
6. **Native Python support** - No external dependency in Python 3.11+

**YAML would be acceptable too**, but switching now would be bikeshedding. Our config is small enough that format choice doesn't matter much.

### If User Insists on YAML

If user strongly prefers YAML after seeing this analysis, switching is easy:

**Migration script**:
```python
import tomllib
import yaml

# Convert
with open("config.toml", "rb") as f:
    data = tomllib.load(f)

with open("config.yaml", "w") as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
```

**Update loaders**:
```python
# Old (TOML)
with open("config.toml", "rb") as f:
    data = tomllib.load(f)

# New (YAML)
with open("config.yaml") as f:
    data = yaml.safe_load(f)
```

**Estimated time**: 2-4 hours for full conversion.

---

## 8. CLI Documentation Generation

### Problem Statement

From user feedback (section 3):
> "how difficult would it be to generate CLI docs automatically? Pretty much every time I worked with the CLI, it was quite tedious because I couldn't remember all the commands so had to step-by-step explore what's available, what the params are, etc. If there was some 'online'/browser-based single-page documentation that of the full CLI surface, that might make things easier to find via Ctrl+F? Maybe even more convenient than auto-complete (though auto-complete in the terminal still would be quite nice to have)?"

**Requirements**:
1. Auto-generated from CLI code (Typer introspection)
2. Single-page HTML document
3. Searchable (Ctrl+F)
4. Shows all commands, parameters, options, help text
5. Easy to regenerate when CLI changes

### Proposed Solution

**Use Typer's introspection + Jinja2 template**

Typer apps expose all command metadata, we can extract and render it.

**Implementation**:

**1. Extract CLI metadata**:

```python
# src/erenshor/cli/docs_generator.py

from typer.main import get_command
import inspect

def extract_cli_metadata(app: Typer) -> dict:
    """Extract all CLI commands, parameters, and help text."""

    # Get Click command from Typer app
    click_app = get_command(app)

    metadata = {
        "name": click_app.name,
        "help": click_app.help,
        "commands": []
    }

    # Extract all commands
    for name, command in click_app.commands.items():
        cmd_meta = {
            "name": name,
            "help": command.help or "No description",
            "usage": command.get_usage(click.Context(command)),
            "options": [],
            "arguments": [],
        }

        # Extract parameters
        for param in command.params:
            param_meta = {
                "name": param.name,
                "type": param.type.name if hasattr(param.type, 'name') else str(param.type),
                "required": param.required,
                "default": param.default,
                "help": param.help or "No description",
            }

            if isinstance(param, click.Option):
                cmd_meta["options"].append(param_meta)
            else:
                cmd_meta["arguments"].append(param_meta)

        metadata["commands"].append(cmd_meta)

    return metadata
```

**2. HTML template**:

```html
<!-- templates/cli_docs.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Erenshor CLI Documentation</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        .search {
            position: sticky;
            top: 0;
            background: white;
            padding: 20px 0;
            border-bottom: 2px solid #eee;
        }
        .search input {
            width: 100%;
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        .command {
            margin: 40px 0;
            padding: 20px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #f9f9f9;
        }
        .command-name {
            font-size: 24px;
            font-weight: bold;
            color: #0066cc;
            margin-bottom: 10px;
        }
        .command-usage {
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Monaco', 'Courier New', monospace;
            overflow-x: auto;
        }
        .param {
            margin: 10px 0;
            padding: 10px;
            background: white;
            border-left: 3px solid #0066cc;
        }
        .param-name {
            font-weight: bold;
            color: #d73a49;
        }
        .required {
            color: #d73a49;
            font-size: 12px;
        }
        .optional {
            color: #6a737d;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <h1>Erenshor CLI Documentation</h1>
    <p>Generated: {{ generated_at }}</p>

    <div class="search">
        <input type="text" id="search" placeholder="Search commands... (Ctrl+F)">
    </div>

    {% for command in commands %}
    <div class="command" data-name="{{ command.name }}">
        <div class="command-name">{{ command.name }}</div>
        <p>{{ command.help }}</p>

        <h3>Usage</h3>
        <div class="command-usage">{{ command.usage }}</div>

        {% if command.arguments %}
        <h3>Arguments</h3>
        {% for arg in command.arguments %}
        <div class="param">
            <span class="param-name">{{ arg.name }}</span>
            <span class="{% if arg.required %}required{% else %}optional{% endif %}">
                {% if arg.required %}REQUIRED{% else %}OPTIONAL{% endif %}
            </span>
            <p>{{ arg.help }}</p>
            {% if arg.default %}
            <p><em>Default: {{ arg.default }}</em></p>
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}

        {% if command.options %}
        <h3>Options</h3>
        {% for opt in command.options %}
        <div class="param">
            <span class="param-name">--{{ opt.name }}</span>
            <span class="optional">OPTIONAL</span>
            <p>{{ opt.help }}</p>
            {% if opt.default %}
            <p><em>Default: {{ opt.default }}</em></p>
            {% endif %}
        </div>
        {% endfor %}
        {% endif %}
    </div>
    {% endfor %}

    <script>
        // Simple client-side search
        document.getElementById('search').addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('.command').forEach(cmd => {
                const text = cmd.textContent.toLowerCase();
                cmd.style.display = text.includes(query) ? 'block' : 'none';
            });
        });
    </script>
</body>
</html>
```

**3. Generator CLI command**:

```python
# src/erenshor/cli/commands/docs.py

@app.command()
def generate_docs(
    output: Path = "docs/cli.html",
    open_browser: bool = True
):
    """Generate CLI documentation as HTML."""

    from jinja2 import Template
    from datetime import datetime

    # Extract metadata from CLI app
    metadata = extract_cli_metadata(app)
    metadata["generated_at"] = datetime.now().isoformat()

    # Load template
    template_path = Path(__file__).parent.parent / "templates" / "cli_docs.html"
    template = Template(template_path.read_text())

    # Render
    html = template.render(**metadata)

    # Write
    output.write_text(html)

    console.print(f"[green]✓[/green] CLI documentation generated: {output}")

    # Open in browser
    if open_browser:
        import webbrowser
        webbrowser.open(output.absolute().as_uri())
```

**4. Usage**:

```bash
# Generate docs
erenshor docs generate

# Output:
# ✓ CLI documentation generated: docs/cli.html
# Opening in browser...
```

**5. Auto-regeneration**:

Add pre-commit hook or CI step to regenerate docs when CLI changes.

```yaml
# .github/workflows/docs.yml
name: Update CLI Docs

on:
  push:
    paths:
      - 'src/erenshor/cli/**'

jobs:
  update-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Generate CLI docs
        run: |
          uv run python -m erenshor.cli.main docs generate --no-open-browser
      - name: Commit updated docs
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add docs/cli.html
          git commit -m "Update CLI documentation" || true
          git push
```

### Alternative: Use Existing Tools

**Option: Typer CLI**

Typer has experimental docs generation:

```bash
typer src/erenshor/cli/main.py utils docs --name erenshor --output docs/cli.md
```

Generates Markdown docs automatically.

**Pros**: Built-in, no custom code
**Cons**: Less control over format, may not have all features we want

### Recommendation

**Implement custom HTML generator** (Option 1) because:
1. Full control over format and styling
2. Single-page, searchable design
3. Can add custom features (examples, categories, etc.)
4. Only ~100 lines of code

**Include in CLI as**:
```bash
erenshor docs generate  # Generate HTML docs
erenshor docs serve     # Serve docs locally (simple HTTP server)
```

### Questions for User

1. **What additional information should docs include**? Examples? Related commands?
2. **Should we also generate Markdown** (for GitHub) or only HTML?
3. **Preferred styling** - minimal/clean vs. rich/colorful?

---

## 9. Docker Feasibility

### Problem Statement

From user feedback (section 3.3):
> "Btw: not quite related but, should we think about dockerizing the project? I think it would be nice to be able to just run things on a new system without a lot of setup overhead but I'm not sure how realistic something like this is with the unity dependency in our stack? Let's discuss that."

**Challenge**: Unity dependency makes containerization complex.

**Question**: Is Docker worth the effort given Unity requirement?

### Unity Dependency Analysis

**Unity Editor Requirements**:
- GUI application (headless batch mode available)
- Large install size (~2-3 GB)
- Requires specific version (2021.3.45f2)
- Linux support exists (Unity officially supports Linux)
- Licensing (Unity Personal is free but requires acceptance)

**Can Unity run in Docker?** Yes, but with caveats:

### Docker Option 1: Full Pipeline Container

**Container includes everything** (Unity, SteamCMD, AssetRipper, Python).

**Dockerfile**:
```dockerfile
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    python3.13 \
    python3-pip

# Install Unity (headless)
RUN wget -qO- https://hub.unity3d.com/linux/repos/deb/key.asc | apt-key add - && \
    echo "deb https://hub.unity3d.com/linux/repos/deb stable main" > /etc/apt/sources.list.d/unity.list && \
    apt-get update && \
    apt-get install -y unity-editor=2021.3.45f2

# Install SteamCMD
RUN wget https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz && \
    tar -xvzf steamcmd_linux.tar.gz && \
    mv steamcmd /usr/local/bin/

# Install Python dependencies
COPY pyproject.toml .
RUN pip install -e .

# Copy application
COPY src/ /app/src/
COPY config.toml /app/

WORKDIR /app
ENTRYPOINT ["erenshor"]
```

**Usage**:
```bash
# Build image
docker build -t erenshor .

# Run extraction
docker run -v $(pwd)/variants:/app/variants erenshor extract

# Run wiki update
docker run -v $(pwd)/variants:/app/variants erenshor wiki update
```

**Pros**:
- Completely reproducible environment
- No local setup needed
- Works on any system with Docker

**Cons**:
- HUGE image size (~5 GB with Unity)
- Slow to build (~30 minutes first time)
- Unity license acceptance required
- Complex to debug
- Might hit Unity licensing issues in container

### Docker Option 2: Separate Unity Container

**Only containerize non-Unity parts**, run Unity locally.

**Dockerfile**:
```dockerfile
FROM python:3.13-slim

# Install SteamCMD, AssetRipper, Python deps
RUN apt-get update && apt-get install -y steamcmd assetripper

COPY pyproject.toml .
RUN pip install -e .

COPY src/ /app/src/
WORKDIR /app

ENTRYPOINT ["erenshor"]
```

**Unity runs on host**:
```bash
# Run download/extract in container
docker run -v $(pwd)/variants:/app/variants erenshor extract download
docker run -v $(pwd)/variants:/app/variants erenshor extract rip

# Run Unity export on host (not containerized)
erenshor extract export

# Run wiki/sheets in container
docker run -v $(pwd)/variants:/app/variants erenshor wiki update
```

**Pros**:
- Smaller image (~500 MB)
- Avoids Unity containerization issues
- Simpler to maintain

**Cons**:
- Still requires Unity on host
- Defeats purpose of full containerization
- More complex workflow

### Docker Option 3: Docker Compose with Services

**Multi-container setup** with separate services.

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  extraction:
    build: ./docker/extraction
    volumes:
      - ./variants:/app/variants
    command: extract

  wiki:
    build: ./docker/wiki
    volumes:
      - ./variants:/app/variants
    depends_on:
      - extraction

  sheets:
    build: ./docker/sheets
    volumes:
      - ./variants:/app/variants
    depends_on:
      - extraction
```

**Usage**:
```bash
docker-compose up extraction  # Run extraction
docker-compose up wiki        # Run wiki updates
```

### Alternative: Development Container (devcontainer)

**VS Code Dev Container** for development environment only.

**.devcontainer/devcontainer.json**:
```json
{
  "name": "Erenshor Development",
  "image": "python:3.13",
  "postCreateCommand": "pip install -e .[dev]",
  "extensions": [
    "ms-python.python",
    "ms-python.vscode-pylance"
  ],
  "mounts": [
    "source=${localWorkspaceFolder}/variants,target=/workspaces/erenshor/variants,type=bind"
  ]
}
```

**Use case**: Consistent dev environment, not for production runs.

**Pros**:
- Simple, focused on development
- VS Code integration
- Still requires Unity on host

**Cons**:
- Doesn't help with production/deployment
- Dev-only solution

### Recommendation

**Don't containerize Unity-dependent parts** for these reasons:

1. **Unity is the blocker** - 5 GB image, licensing, slow builds
2. **Limited benefit** - Unity still requires local installation for dev work
3. **Solo dev context** - Not deploying to production servers
4. **YAGNI** - Setup on new system is infrequent (how often?)

**Do containerize outputs** (wiki, sheets, maps):

**Lightweight container for outputs only**:

```dockerfile
# Dockerfile
FROM python:3.13-slim

COPY src/erenshor /app/erenshor
COPY pyproject.toml /app/
WORKDIR /app

RUN pip install -e .

ENTRYPOINT ["python", "-m", "erenshor.cli.main"]
```

**Usage**:
```bash
# After extraction is done (Unity runs on host)
docker run -v $(pwd)/variants:/app/variants erenshor wiki update
docker run -v $(pwd)/variants:/app/variants erenshor sheets deploy
```

**Benefits**:
- Small image (~200 MB)
- Fast to build (~1 minute)
- Useful for CI/CD (if we add it later)
- No Unity dependency

### Future: Cloud Execution

If we ever need to run Unity in cloud:
- Use GitHub Actions with Unity pre-installed runner
- Use cloud VMs with Unity pre-installed
- Use Unity Cloud Build (paid service)

**Not worth it for solo dev project.**

### Questions for User

1. **How often do you set up on new systems?** Once a year? More?
2. **Primary pain point in setup** - Unity install? Python deps? Configuration?
3. **Would dev container help**? (VS Code integration)

---

## 10. Test Database Approach

### Problem Statement

From user feedback (section 9.2):
> "Beware that constructing a test DB is hard work and often produces cases that don't quite match real-world scenarios due to some subtle differences. An option might be to just copy the current, most recent DB and use that for implementation of integration tests going forward. We can still update things as needed over time. What do you think? Is this proper testing practice? Or should be go with a different solution?"

**Question**: Should we use real production database copy for tests, or construct minimal test data?

### Testing Approaches

**Option 1: Real Database Copy (User's Suggestion)**

Copy current production database and use for all tests.

```python
# tests/conftest.py

@pytest.fixture(scope="session")
def test_db():
    """Provide real production database for tests."""

    # Copy current production DB to test location
    prod_db = Path("variants/main/erenshor-main.sqlite")
    test_db = Path("tests/fixtures/test_database.sqlite")

    if not test_db.exists():
        shutil.copy(prod_db, test_db)

    return test_db

# Test using real data
def test_generate_item_page(test_db):
    page = generate_item_page(test_db, item_id=123)  # Real item ID
    assert "{{Item Infobox" in page
```

**Pros**:
- **Real-world data** - Tests use actual game data
- **Comprehensive** - Covers edge cases naturally
- **Easy to create** - Just copy file
- **No construction needed** - No manual test data creation

**Cons**:
- **Large** - 20 MB database, slow to load
- **Brittle** - Tests depend on specific IDs/names that might change
- **Unclear intent** - What is test trying to verify?
- **Coverage unclear** - Are we testing all edge cases?
- **Hard to debug** - Why did test fail? Which data caused it?

**Option 2: Minimal Test Database**

Construct small database with only essential test data.

```python
@pytest.fixture
def test_db():
    """Create minimal test database."""

    db = sqlite3.connect(":memory:")

    # Create schema
    db.execute("""
        CREATE TABLE Items (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slot TEXT,
            required_level INTEGER,
            ...
        )
    """)

    # Insert minimal test data
    db.execute("""
        INSERT INTO Items (id, name, slot, required_level)
        VALUES
            (1, 'Test Sword', 'MainHand', 1),
            (2, 'Test Shield', 'OffHand', 5),
            (3, 'Test Armor', 'Chest', 10)
    """)

    return db
```

**Pros**:
- **Fast** - In-memory, tiny dataset
- **Clear intent** - Test data is explicit
- **Focused** - Only includes what test needs
- **Easy to debug** - Small dataset, clear what's being tested

**Cons**:
- **Manual work** - Need to construct test data
- **Might miss edge cases** - Don't have full variety of real data
- **Maintenance** - Need to update as schema changes

**Option 3: Hybrid (Recommended)**

Use real database for integration tests, minimal database for unit tests.

```python
# Unit tests: Minimal, focused data
@pytest.fixture
def minimal_db():
    """Small, in-memory database for unit tests."""
    db = sqlite3.connect(":memory:")
    # Minimal schema and data
    return db

def test_item_classification(minimal_db):
    """Fast unit test with minimal data."""
    result = classify_item(minimal_db, item_id=1)
    assert result == "weapon"

# Integration tests: Real database
@pytest.fixture(scope="session")
def real_db():
    """Real production database for integration tests."""
    return Path("tests/fixtures/erenshor-test.sqlite")

def test_generate_all_item_pages(real_db):
    """Integration test with real data."""
    pages = generate_all_item_pages(real_db)
    assert len(pages) > 100  # Has real amount of data
    # Spot check a few pages
    assert "{{Item Infobox" in pages["Sword"]
```

**Pros**:
- **Best of both worlds** - Fast unit tests, comprehensive integration tests
- **Clear separation** - Unit vs. integration
- **Flexible** - Can use appropriate data for each test

**Cons**:
- **More complex** - Two fixtures to maintain
- **Still need to construct minimal data** - But less of it

### Recommendation

**Use Option 3 (Hybrid Approach)**:

**Test Pyramid**:
```
Unit Tests (60%) - Minimal test data
    ↑ Fast, focused, many tests

Integration Tests (30%) - Real database copy
    ↑ Slower, comprehensive, fewer tests

E2E Tests (10%) - Real database + real outputs
    ↑ Slowest, full workflow, rare
```

**Implementation**:

**1. Fixtures**:

```python
# tests/conftest.py

import pytest
from pathlib import Path
import sqlite3
import shutil

# Minimal database for unit tests
@pytest.fixture
def minimal_db():
    """In-memory database with minimal test data."""
    db = sqlite3.connect(":memory:")

    # Load schema
    schema = Path("tests/fixtures/test_schema.sql").read_text()
    db.executescript(schema)

    # Load minimal test data
    test_data = Path("tests/fixtures/test_data.sql").read_text()
    db.executescript(test_data)

    yield db
    db.close()

# Real database for integration tests
@pytest.fixture(scope="session")
def real_db():
    """Real production database copy (session-scoped for performance)."""
    test_db_path = Path("tests/fixtures/erenshor-test.sqlite")

    # Copy from production if doesn't exist or is outdated
    if not test_db_path.exists():
        prod_db = Path("variants/main/erenshor-main.sqlite")
        if prod_db.exists():
            shutil.copy(prod_db, test_db_path)
        else:
            pytest.skip("Production database not available")

    yield test_db_path

# Pytest marks for test types
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (fast)")
    config.addinivalue_line("markers", "integration: Integration tests (slower)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (slowest)")
```

**2. Test Organization**:

```
tests/
├── unit/                    # Fast, minimal data
│   ├── test_classifiers.py
│   ├── test_formatters.py
│   └── test_utils.py
├── integration/             # Real database
│   ├── test_wiki_generation.py
│   ├── test_sheets_export.py
│   └── test_registry.py
├── e2e/                     # Full workflows
│   └── test_full_pipeline.py
└── fixtures/
    ├── test_schema.sql      # Minimal schema
    ├── test_data.sql        # Minimal test data
    └── erenshor-test.sqlite # Real DB copy (gitignored)
```

**3. Running Tests**:

```bash
# Fast: Only unit tests
pytest -m unit

# Slower: Only integration tests
pytest -m integration

# All tests
pytest

# Specific test file
pytest tests/unit/test_classifiers.py
```

**4. Real Database Maintenance**:

```bash
# Update test database from current production
cp variants/main/erenshor-main.sqlite tests/fixtures/erenshor-test.sqlite

# Or via CLI command
erenshor test update-db
```

### Is This Proper Practice?

**Yes, using real database copy for integration tests is acceptable and common**:

1. **Industry practice** - Many projects do this (called "snapshot testing" or "golden file testing")
2. **Pragmatic** - Better than no tests or incomplete test data
3. **Catches real issues** - Tests use actual game data with all its quirks
4. **Maintainable** - Easy to update (just copy new database)

**Best practices for using real DB in tests**:

1. **Pin specific IDs/names** - Don't rely on "first item" but on specific known items
2. **Add regression fixtures** - When bugs found, add specific cases to minimal DB
3. **Update regularly** - Keep test DB in sync with production
4. **Document dependencies** - Tests should clearly state which data they need
5. **Use session scope** - Load real DB once per test session for performance

### Example Tests

**Unit test (minimal data)**:

```python
@pytest.mark.unit
def test_classify_weapon(minimal_db):
    """Test item classification with known data."""

    # Test DB has item ID=1 as "Test Sword"
    item_kind = classify_item_kind(minimal_db, item_id=1)

    assert item_kind == "weapon"
```

**Integration test (real data)**:

```python
@pytest.mark.integration
def test_generate_character_page_for_goblin_warrior(real_db):
    """Test page generation with real game data."""

    # Use actual character from game
    page = generate_character_page(real_db, character_id=123)  # Known Goblin Warrior

    # Verify structure
    assert "{{Character Infobox" in page
    assert "Goblin Warrior" in page
    assert "Level" in page

    # Verify specific fields
    assert "Health:" in page
    assert "Damage:" in page
```

### Questions for User

1. **Should we commit test database to git** (20 MB) or gitignore it?
2. **How often should we update test DB** - weekly? monthly? on demand?
3. **Any specific known edge cases** we should add to minimal test DB?

---

## Summary

This document provides detailed analysis and concrete proposals for 10 critical issues raised in user feedback. Each issue includes:
- Problem statement
- Multiple options with pros/cons
- Concrete implementation details
- Recommendations
- Questions for user to make final decisions

**Next steps**: User reviews proposals, makes decisions, and we proceed with implementation.
