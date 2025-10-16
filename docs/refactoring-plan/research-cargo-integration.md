# MediaWiki Cargo Integration Research

**Date**: 2025-10-16
**Status**: Research Complete
**Recommendation**: Implement Cargo Now (with phased rollout)

---

## Executive Summary

MediaWiki Cargo is a **must-have** extension for the Erenshor wiki project. After thorough research, the recommendation is to **implement Cargo integration now** as part of the current template generation refactor. Deferring Cargo to the backlog would require significant rework later, as it fundamentally changes how templates store and query data.

**Key Finding**: Cargo integration requires minimal changes to our existing architecture but must be designed into templates from the start. Adding it later would require regenerating all pages and restructuring templates.

---

## What is MediaWiki Cargo?

### Overview

Cargo is a MediaWiki extension that provides structured data storage and querying capabilities. It stores template data in database tables, enabling:

- **Structured queries** across wiki pages
- **Dynamic lists and tables** that auto-update when data changes
- **Complex relationships** (one-to-many, many-to-many)
- **Data aggregation** (stats, counts, summaries)
- **Cross-page references** without manual maintenance

### Core Concepts

Cargo operates through three parser functions embedded in templates:

1. **`#cargo_declare`**: Defines database table schema (placed in template `<noinclude>` section)
2. **`#cargo_store`**: Stores data when page is rendered (placed in template `<includeonly>` section)
3. **`#cargo_query`**: Queries stored data from any page on the wiki

### Example: Simple Item Template

```wikitext
<noinclude>
{{#cargo_declare:_table=Items
|Name=String
|Type=String
|Level=Integer
|Damage=String
|Classes=List (,) of String
|Source=Text
}}
</noinclude>
<includeonly>
{{#cargo_store:_table=Items
|Name={{{title|}}}
|Type={{{type|}}}
|Level={{{level|}}}
|Damage={{{damage|}}}
|Classes={{{classes|}}}
|Source={{{source|}}}
}}
</includeonly>

{| class="wikitable infobox"
! colspan="2" | {{{title|}}}
|-
| '''Type''' || {{{type|}}}
|-
| '''Level''' || {{{level|}}}
|-
| '''Damage''' || {{{damage|}}}
|-
| '''Classes''' || {{{classes|}}}
|}
```

### Why Cargo is Essential for Gaming Wikis

Gaming wikis have **inherently relational data**:

- Items dropped by enemies
- Abilities used by characters
- Recipes requiring ingredients
- Quests rewarding items
- Vendors selling items

Without Cargo, these relationships must be maintained manually in both directions:
- Enemy page lists drops → Manual
- Item page lists sources → Manual
- Recipe page lists ingredients → Manual
- Ingredient page lists uses → Manual

With Cargo, relationships are stored once and queried dynamically:
- Enemy page stores drops → Automatic
- Item page queries "WHERE Item = this page" → Automatic
- Recipe page stores ingredients → Automatic
- Ingredient page queries "WHERE Ingredient = this page" → Automatic

---

## Architectural Design for Erenshor

### Current Architecture

The Erenshor project uses a **generator-based architecture**:

```
Database (SQLite)
    ↓
Generator (Python)
    ↓
Template Context (Pydantic)
    ↓
Jinja2 Template
    ↓
WikiText Output
    ↓
MediaWiki API Upload
```

Generators like `CharacterGenerator` query the SQLite database, build context objects, render Jinja2 templates, and output pure wikitext.

### Proposed Cargo Architecture

Cargo integration requires **minimal changes** to this architecture:

```
Database (SQLite)
    ↓
Generator (Python)
    ↓
Template Context (Pydantic) [UNCHANGED]
    ↓
Jinja2 Template [MODIFIED: Add #cargo_store calls]
    ↓
WikiText Output [MODIFIED: Includes Cargo storage]
    ↓
MediaWiki API Upload
    ↓
Cargo Database [NEW: MediaWiki extension stores data]
```

**Key insight**: Our generators already produce all the data Cargo needs. We just need to:
1. Add `#cargo_declare` to template `<noinclude>` sections
2. Add `#cargo_store` to template `<includeonly>` sections
3. Optionally add `#cargo_query` for dynamic sections

### Integration Points

#### 1. Template Schema Definition

Each template needs a Cargo schema that mirrors our Pydantic context models:

**Current: `EnemyInfoboxContext` (Python)**
```python
class EnemyInfoboxContext(BaseModel):
    name: str
    image: str
    type: str
    faction: str
    zones: str
    level: str
    health: str
    # ... 20+ more fields
```

**Proposed: `Template:Enemy` (WikiText)**
```wikitext
<noinclude>
{{#cargo_declare:_table=Enemies
|Name=String
|Image=File
|Type=String
|Faction=Page
|Zones=List (,) of Page
|Level=Integer
|Health=Integer
|Mana=Integer
|AC=Integer
|Strength=Integer
|Endurance=Integer
|Dexterity=Integer
|Agility=Integer
|Intelligence=Integer
|Wisdom=Integer
|Charisma=Integer
|MagicResist=String
|ElementalResist=String
|PoisonResist=String
|VoidResist=String
|Coordinates=String
|SpawnChance=String
|Respawn=String
|Experience=String
}}
</noinclude>
```

#### 2. Template Storage Calls

Our Jinja2 templates already output all parameter values. We need to add corresponding `#cargo_store` calls:

**Current: `characters/enemy.j2`**
```jinja
{{ "{{" }}Enemy
|name={{ ctx.name }}
|image=[[File:{{ ctx.image }}|thumb]]
|type={{ ctx.type }}
|faction={{ ctx.faction }}
|zones={{ ctx.zones }}
|level={{ ctx.level }}
|health={{ ctx.health }}
{{ "}}" }}
```

**Proposed: `characters/enemy.j2` (with Cargo)**
```jinja
{{ "{{" }}Enemy
|name={{ ctx.name }}
|image=[[File:{{ ctx.image }}|thumb]]
|type={{ ctx.type }}
|faction={{ ctx.faction }}
|zones={{ ctx.zones }}
|level={{ ctx.level }}
|health={{ ctx.health }}
{{ "}}" }}

{{ "{{" }}#cargo_store:_table=Enemies
|Name={{ ctx.name }}
|Image={{ ctx.image }}
|Type={{ ctx.type }}
|Faction={{ ctx.faction }}
|Zones={{ ctx.zones }}
|Level={{ ctx.level }}
|Health={{ ctx.health }}
|Mana={{ ctx.mana }}
|AC={{ ctx.ac }}
|Strength={{ ctx.strength }}
|Endurance={{ ctx.endurance }}
|Dexterity={{ ctx.dexterity }}
|Agility={{ ctx.agility }}
|Intelligence={{ ctx.intelligence }}
|Wisdom={{ ctx.wisdom }}
|Charisma={{ ctx.charisma }}
|MagicResist={{ ctx.magic }}
|ElementalResist={{ ctx.elemental }}
|PoisonResist={{ ctx.poison }}
|VoidResist={{ ctx.void }}
|Coordinates={{ ctx.coordinates }}
|SpawnChance={{ ctx.spawnchance }}
|Respawn={{ ctx.respawn }}
|Experience={{ ctx.experience }}
{{ "}}" }}
```

#### 3. Relationship Tables (Junction Tables)

Erenshor's database uses junction tables for many-to-many relationships:
- `CharacterAttackSpells`: Characters → Spells
- `CharacterBuffSpells`: Characters → Spells
- `LootTableEntries`: Characters → Items
- `SpawnPointCharacters`: SpawnPoints → Characters

Cargo handles these through **separate tables** with foreign key relationships:

**Example: Character Drops**

```wikitext
<!-- In Template:Enemy -->
{{#cargo_declare:_table=Enemies
|Name=String (primary key)
|Level=Integer
}}

{{#cargo_declare:_table=EnemyDrops
|Enemy=Page
|Item=Page
|DropChance=Float
|GuaranteedDrop=Boolean
}}

<!-- When rendering enemy page -->
{{#cargo_store:_table=Enemies
|Name=Giant Spider
|Level=15
}}

<!-- For each drop -->
{{#cargo_store:_table=EnemyDrops
|Enemy=Giant Spider
|Item=Spider Silk
|DropChance=25.0
|GuaranteedDrop=No
}}
```

**Querying drops on Item page**:
```wikitext
<!-- On "Spider Silk" item page, show which enemies drop it -->
{{#cargo_query:
tables=EnemyDrops
|fields=Enemy,DropChance
|where=Item='{{PAGENAME}}'
|format=ul
}}
```

This automatically generates:
- Giant Spider (25%)
- Cave Spider (15%)
- Spider Queen (100%)

#### 4. Multiple Cargo Stores per Page

Our generators often produce **multiple related blocks** per page. Cargo supports this through multiple `#cargo_store` calls:

**Example: Character with Multiple Spawn Locations**

```jinja
{{ "{{" }}Enemy
|name={{ ctx.name }}
|level={{ ctx.level }}
{{ "}}" }}

{{ "{{" }}#cargo_store:_table=Enemies
|Name={{ ctx.name }}
|Level={{ ctx.level }}
{{ "}}" }}

{% for spawn in ctx.spawn_points %}
{{ "{{" }}#cargo_store:_table=EnemySpawns
|Enemy={{ ctx.name }}
|Zone={{ spawn.zone }}
|Coordinates={{ spawn.coordinates }}
|Respawn={{ spawn.respawn }}
|SpawnChance={{ spawn.chance }}
{{ "}}" }}
{% endfor %}

{% for drop in ctx.drops %}
{{ "{{" }}#cargo_store:_table=EnemyDrops
|Enemy={{ ctx.name }}
|Item={{ drop.item_name }}
|DropChance={{ drop.chance }}
|GuaranteedDrop={{ drop.guaranteed }}
{{ "}}" }}
{% endfor %}
```

### Cargo Table Schema Design

Based on Erenshor's domain entities, we need the following Cargo tables:

#### Core Entity Tables

| Table | Description | Key Fields |
|-------|-------------|------------|
| `Enemies` | Character/NPC/Enemy base stats | Name, Type, Level, Health, Mana, Stats, Resistances |
| `Items` | Item base stats | Name, Type, Level, Damage, Delay, DPS, Effects, Buy, Sell |
| `Abilities` | Spell/Skill base stats | Name, Type, Level, Cost, CastTime, Cooldown, Duration, Damage |
| `Factions` | Faction information | Name, Description |
| `Zones` | Zone/area information | Name, Level, Type |

#### Relationship Tables (Junction)

| Table | Description | Key Fields |
|-------|-------------|------------|
| `EnemySpawns` | Enemy spawn locations | Enemy (Page), Zone (Page), Coordinates, Respawn, SpawnChance |
| `EnemyDrops` | Enemy loot tables | Enemy (Page), Item (Page), DropChance, GuaranteedDrop |
| `EnemyAbilities` | Enemy abilities | Enemy (Page), Ability (Page), AbilityType (String) |
| `EnemyFactions` | Enemy faction relationships | Enemy (Page), Faction (Page), Modifier (Integer) |
| `ItemSources` | Item sources | Item (Page), Source (String), SourceType (String) |
| `ItemClasses` | Item class restrictions | Item (Page), Class (String) |
| `ItemComponents` | Item crafting recipes | Item (Page), Component (Page), Quantity (Integer) |
| `AbilityClasses` | Ability class restrictions | Ability (Page), Class (String) |
| `VendorItems` | Vendor inventories | Vendor (Page), Item (Page), Price (Integer) |

#### Data Types

Cargo supports these field types (mapping to our data):

| Cargo Type | Use Case | Example |
|------------|----------|---------|
| `String` | Short text, IDs | Name, Type, Rarity |
| `Text` | Long text, descriptions | Item descriptions, quest text |
| `Integer` | Whole numbers | Level, Health, Damage |
| `Float` | Decimals | Drop chance, spawn chance, multipliers |
| `Boolean` | Yes/No | IsUnique, IsBoss, GuaranteedDrop |
| `Date` | Dates | (Not used in Erenshor) |
| `Datetime` | Timestamps | (Not used in Erenshor) |
| `Page` | Wiki page reference | Enemy, Item, Ability (for links) |
| `File` | File reference | Image filenames |
| `List (,) of Type` | Multiple values | Classes, Zones, Abilities |
| `Coordinates` | Geographic coordinates | (Not used - we use String for game coords) |

---

## Template Structure with Cargo

### Complete Example: Enemy Template

**File**: `src/erenshor/templates/characters/enemy.j2`

```jinja
{# Cargo table declaration - only rendered in Template namespace #}
<noinclude>
{{#cargo_declare:_table=Enemies
|Name=String
|Image=File
|Type=String
|Faction=Page
|Zones=List (,) of Page
|Coordinates=String
|SpawnChance=String
|Respawn=String
|Level=Integer
|Experience=String
|Health=Integer
|Mana=Integer
|AC=Integer
|Strength=Integer
|Endurance=Integer
|Dexterity=Integer
|Agility=Integer
|Intelligence=Integer
|Wisdom=Integer
|Charisma=Integer
|MagicResist=String
|ElementalResist=String
|PoisonResist=String
|VoidResist=String
}}

{{#cargo_declare:_table=EnemyDrops
|Enemy=Page
|Item=Page
|DropChance=Float
|GuaranteedDrop=Boolean
}}

{{#cargo_declare:_table=EnemySpawns
|Enemy=Page
|Zone=Page
|Coordinates=String
|Respawn=String
|SpawnChance=String
}}

{{#cargo_declare:_table=EnemyFactions
|Enemy=Page
|Faction=Page
|Modifier=Integer
}}
</noinclude>

{# Template invocation - rendered on every page #}
<includeonly>
{# Store enemy base stats #}
{{#cargo_store:_table=Enemies
|Name={{{name|}}}
|Image={{{image|}}}
|Type={{{type|}}}
|Faction={{{faction|}}}
|Zones={{{zones|}}}
|Coordinates={{{coordinates|}}}
|SpawnChance={{{spawnchance|}}}
|Respawn={{{respawn|}}}
|Level={{{level|}}}
|Experience={{{experience|}}}
|Health={{{health|}}}
|Mana={{{mana|}}}
|AC={{{ac|}}}
|Strength={{{strength|}}}
|Endurance={{{endurance|}}}
|Dexterity={{{dexterity|}}}
|Agility={{{agility|}}}
|Intelligence={{{intelligence|}}}
|Wisdom={{{wisdom|}}}
|Charisma={{{charisma|}}}
|MagicResist={{{magic|}}}
|ElementalResist={{{elemental|}}}
|PoisonResist={{{poison|}}}
|VoidResist={{{void|}}}
}}

{# Visual display - unchanged from current implementation #}
{{Enemy
|name={{{name|}}}
|image={{{image|}}}
|imagecaption={{{imagecaption|}}}
|type={{{type|}}}
|faction={{{faction|}}}
|factionChange={{{factionChange|}}}
|zones={{{zones|}}}
|coordinates={{{coordinates|}}}
|spawnchance={{{spawnchance|}}}
|respawn={{{respawn|}}}
|guaranteeddrops={{{guaranteeddrops|}}}
|droprates={{{droprates|}}}
|level={{{level|}}}
|experience={{{experience|}}}
|health={{{health|}}}
|mana={{{mana|}}}
|ac={{{ac|}}}
|strength={{{strength|}}}
|endurance={{{endurance|}}}
|dexterity={{{dexterity|}}}
|agility={{{agility|}}}
|intelligence={{{intelligence|}}}
|wisdom={{{wisdom|}}}
|charisma={{{charisma|}}}
|magic={{{magic|}}}
|poison={{{poison|}}}
|elemental={{{elemental|}}}
|void={{{void|}}}
}}
</includeonly>
```

**Generated Output** (on page "Giant Spider"):

```wikitext
{{#cargo_store:_table=Enemies
|Name=Giant Spider
|Image=Giant_Spider.png
|Type=[[Enemies|Enemy]]
|Faction=[[The Followers of Evil]]
|Zones=[[Misty Vale]]
|Level=15
|Health=450
|Mana=0
|AC=120
|Strength=45
|Endurance=40
|Dexterity=30
|Agility=25
|Intelligence=5
|Wisdom=5
|Charisma=5
|MagicResist=10-15
|ElementalResist=5-10
|PoisonResist=50-60
|VoidResist=0
|Coordinates=123.4 x 56.7 x 89.0
|SpawnChance=25%
|Respawn=10 minutes
|Experience=350-420
}}

{{Enemy
|name=Giant Spider
|image=[[File:Giant_Spider.png|thumb]]
|type=[[Enemies|Enemy]]
|faction=[[The Followers of Evil]]
|zones=[[Misty Vale]]
|level=15
|health=450
|...
}}
```

### Example: Dynamic Drop List on Item Page

**Scenario**: Item page "Spider Silk" shows which enemies drop it

**Implementation**:

```wikitext
== Dropped By ==

{{#cargo_query:
tables=EnemyDrops,Enemies
|join on=EnemyDrops.Enemy=Enemies.Name
|fields=EnemyDrops.Enemy=Enemy,Enemies.Level=Level,EnemyDrops.DropChance=Chance,EnemyDrops.GuaranteedDrop=Guaranteed
|where=EnemyDrops.Item='{{PAGENAME}}'
|order by=Enemies.Level ASC,EnemyDrops.DropChance DESC
|format=table
|headers=Enemy,Level,Drop Chance,Guaranteed
}}
```

**Output** (auto-generated, always up-to-date):

| Enemy | Level | Drop Chance | Guaranteed |
|-------|-------|-------------|------------|
| [[Small Spider]] | 5 | 10% | No |
| [[Giant Spider]] | 15 | 25% | No |
| [[Cave Spider]] | 20 | 15% | No |
| [[Spider Queen]] | 35 | 100% | Yes |

**Key Benefit**: When we add a new enemy that drops Spider Silk, this table updates automatically. No manual edits required.

### Example: Zone Enemy List

**Scenario**: Zone page "Misty Vale" shows all enemies in that zone

**Implementation**:

```wikitext
== Enemies ==

{{#cargo_query:
tables=EnemySpawns,Enemies
|join on=EnemySpawns.Enemy=Enemies.Name
|fields=Enemies.Name=Enemy,Enemies.Level=Level,Enemies.Type=Type,EnemySpawns.Respawn=Respawn
|where=EnemySpawns.Zone='{{PAGENAME}}'
|order by=Enemies.Level ASC
|format=table
}}
```

**Output**:

| Enemy | Level | Type | Respawn |
|-------|-------|------|---------|
| [[Young Wolf]] | 3 | Enemy | 5 minutes |
| [[Forest Bear]] | 8 | Enemy | 10 minutes |
| [[Giant Spider]] | 15 | Enemy | 10 minutes |
| [[Ancient Treant]] | 25 | Boss | 30 minutes |

---

## Implementation Approach: NOW vs BACKLOG

### Analysis: Can Cargo Be Added Later?

**Answer**: Technically yes, but with **significant overhead**.

**Reasons to integrate NOW**:

1. **Template Structure Changes**: Adding Cargo later requires modifying every template to include `#cargo_declare` and `#cargo_store` calls. This means:
   - Regenerating all wiki pages
   - Re-uploading all pages
   - Testing all templates
   - Validating all Cargo schemas

2. **Schema Design is Upfront Work**: Designing Cargo table schemas (field names, types, relationships) must happen before templates are deployed. Changing schemas later requires:
   - Recreating Cargo tables (data loss)
   - Updating all template calls
   - Regenerating and re-uploading all pages

3. **Minimal Additional Cost Now**: Our generators already produce all necessary data. Adding Cargo calls to Jinja2 templates is straightforward:
   - Add `#cargo_declare` to template `<noinclude>` sections (one-time per template)
   - Add `#cargo_store` to Jinja2 templates (mirrors existing template parameters)
   - No changes to Python generators required
   - No changes to Pydantic contexts required

4. **Future Features Depend on Cargo**: Many wiki improvements require Cargo:
   - Dynamic lists (items by level, enemies by zone, etc.)
   - Cross-references (where is this item used?)
   - Statistics pages (total items, enemies per zone, etc.)
   - Search and filtering
   - Without Cargo, these features require manual maintenance or complex bots

5. **Wiki Maintainer Benefit**: Cargo makes manual editing easier:
   - Adding a new enemy drop? Just add one `{{#cargo_store}}` call to the enemy page
   - Item page's "Dropped By" section updates automatically
   - No need to manually update both enemy and item pages

6. **User Expectation**: Modern gaming wikis use structured data (Cargo or Semantic MediaWiki). Users expect:
   - Dynamic sortable tables
   - Cross-page queries
   - Automatic relationship tracking
   - Without Cargo, the Erenshor wiki feels outdated

**Reasons to defer to BACKLOG**:

1. **Extension Installation**: Requires MediaWiki admin access to install Cargo extension
   - **Counter**: This is a one-time setup, not a recurring cost
   - **Counter**: Installation is straightforward (documented, well-supported extension)

2. **Testing Complexity**: Need to test Cargo table creation, data storage, and querying
   - **Counter**: Cargo is mature and well-tested (used by major wikis)
   - **Counter**: Testing can be done on local/dev wiki before production

3. **Initial Time Investment**: Designing schemas and updating templates takes time
   - **Counter**: This work is required eventually; doing it now avoids rework
   - **Counter**: Schema design parallels our existing Pydantic models (direct mapping)

**Verdict**: **Implement Cargo NOW**

The overhead of adding Cargo later (regenerating and re-uploading all pages) exceeds the cost of integrating it now. Our architecture already supports Cargo with minimal changes.

---

## Implementation Plan (Now)

### Phase 1: Foundation (Week 1)

**Goal**: Establish Cargo infrastructure and test with one entity type

**Tasks**:

1. **Install Cargo Extension**
   - Install MediaWiki Cargo extension on wiki
   - Verify API access and permissions
   - Test basic `#cargo_declare` and `#cargo_store` functionality

2. **Design Core Table Schemas**
   - Map Pydantic context models to Cargo schemas
   - Define field names, types, and relationships
   - Document schema in `docs/cargo-schemas.md`

3. **Create Cargo Template Module**
   - New module: `src/erenshor/infrastructure/templates/cargo.py`
   - Function: `generate_cargo_declare()` - Converts Pydantic model to `#cargo_declare` call
   - Function: `generate_cargo_store()` - Converts context instance to `#cargo_store` call
   - Unit tests for schema generation

4. **Integrate Cargo into One Template**
   - Choose: `Template:Enemy` (well-tested, stable)
   - Update `characters/enemy.j2` to include Cargo calls
   - Test: Generate enemy pages with Cargo
   - Verify: Check Cargo tables populate correctly

**Deliverables**:
- Cargo extension installed and tested
- Schema documentation (`docs/cargo-schemas.md`)
- Cargo template module with tests
- One template (Enemy) with Cargo integration
- Test report validating Cargo storage

**Success Criteria**:
- Enemy pages render correctly
- Cargo table `Enemies` populates with correct data
- Basic Cargo query works: `{{#cargo_query:tables=Enemies|fields=Name,Level}}`

### Phase 2: Core Entity Expansion (Week 2)

**Goal**: Integrate Cargo into all core entity templates

**Tasks**:

1. **Items Template**
   - Update `items/item.j2` with Cargo schema
   - Create `Items` table
   - Handle item subtypes (weapons, armor, consumables, molds, etc.)
   - Test: Generate item pages, verify storage

2. **Abilities Template**
   - Update `abilities/ability.j2` with Cargo schema
   - Create `Abilities` table
   - Handle ability subtypes (spells, skills)
   - Test: Generate ability pages, verify storage

3. **Factions Template**
   - Create Cargo schema for factions
   - Update faction rendering (if exists)
   - Test: Store faction data

4. **Zones Template**
   - Create Cargo schema for zones
   - Update zone rendering (if exists)
   - Test: Store zone data

**Deliverables**:
- All core entity templates have Cargo integration
- All core Cargo tables created and populated
- Test report for each entity type

**Success Criteria**:
- All entity pages render correctly
- All Cargo tables populate correctly
- Data accuracy: Spot-check 10% of entries against database

### Phase 3: Relationship Tables (Week 3)

**Goal**: Implement junction tables for entity relationships

**Tasks**:

1. **Enemy Drops**
   - Create `EnemyDrops` table
   - Update `CharacterGenerator` to output multiple `#cargo_store` calls for drops
   - Test: Query drops on item pages

2. **Enemy Spawns**
   - Create `EnemySpawns` table
   - Update `CharacterGenerator` to store spawn data
   - Test: Query spawns on zone pages

3. **Enemy Abilities**
   - Create `EnemyAbilities` table
   - Update `CharacterGenerator` to store ability relationships
   - Test: Query abilities on ability pages

4. **Item Sources**
   - Create `ItemSources` table (vendors, quests, crafting)
   - Update `ItemGenerator` to store sources
   - Test: Query sources on NPC pages

5. **Item Recipes**
   - Create `ItemComponents` table
   - Update `ItemGenerator` to store crafting recipes
   - Test: Query "used in" on component pages

**Deliverables**:
- All relationship tables implemented
- Generators updated to output relationship data
- Cross-page queries working

**Success Criteria**:
- Enemy pages show drops
- Item pages show drop sources (via Cargo query)
- Zone pages show enemy lists (via Cargo query)
- Crafting pages show ingredient uses (via Cargo query)

### Phase 4: Dynamic Queries (Week 4)

**Goal**: Add dynamic content to overview pages using Cargo queries

**Tasks**:

1. **Zone Pages**
   - Add enemy list (from `EnemySpawns`)
   - Add drop list (from `EnemyDrops` + `EnemySpawns`)
   - Add level range (from `Enemies`)

2. **Item Category Pages**
   - Add sortable item tables (by level, type, etc.)
   - Add filtering (by class, slot, etc.)

3. **Enemy Category Pages**
   - Add sortable enemy tables (by level, zone, type)
   - Add filtering (by faction, type)

4. **Statistics Pages**
   - Create "Statistics" page with aggregate queries
   - Item count by type
   - Enemy count by zone
   - Average stats by level
   - Drop rate statistics

**Deliverables**:
- Overview pages with dynamic Cargo content
- Statistics pages with aggregate queries
- User documentation for Cargo queries

**Success Criteria**:
- Overview pages auto-update when entities change
- Sorting and filtering works correctly
- Statistics are accurate

### Phase 5: Testing & Documentation (Week 5)

**Goal**: Validate Cargo integration, optimize performance, document usage

**Tasks**:

1. **Integration Testing**
   - Full pipeline test: Database → Generator → Template → Wiki → Cargo
   - Verify all entity types
   - Verify all relationships
   - Check for missing data

2. **Performance Testing**
   - Test Cargo query performance with full dataset
   - Optimize slow queries (indexes, query structure)
   - Test page load times

3. **Manual Edit Testing**
   - Test adding new entity manually via wiki
   - Test updating entity manually
   - Verify Cargo stores manual edits correctly

4. **Documentation**
   - Update `CLAUDE.md` with Cargo architecture
   - Create `docs/CARGO_INTEGRATION.md` user guide
   - Create `docs/CARGO_QUERIES.md` query examples
   - Document troubleshooting steps

5. **Wiki Maintainer Guide**
   - Create guide for manual editors
   - How to add/edit entities with Cargo
   - Common Cargo queries for maintainers
   - Troubleshooting guide

**Deliverables**:
- Complete test report
- Performance optimization report
- User documentation
- Maintainer guide

**Success Criteria**:
- 100% entity types have Cargo integration
- 100% relationship tables implemented
- All tests pass
- Documentation complete

### Phase 6: Production Deployment (Week 6)

**Goal**: Deploy Cargo-enabled templates to production wiki

**Tasks**:

1. **Template Deployment**
   - Upload all templates with Cargo declarations to wiki
   - Verify templates render correctly

2. **Table Creation**
   - Run "Recreate data" on all templates
   - Verify tables created successfully
   - Verify data populated correctly

3. **Page Generation**
   - Run full update pipeline with Cargo-enabled templates
   - Upload all pages to wiki
   - Verify pages render correctly
   - Verify Cargo storage working

4. **Query Validation**
   - Test all Cargo queries on production wiki
   - Verify results match expectations
   - Fix any query issues

5. **Monitoring**
   - Monitor Cargo table sizes
   - Monitor query performance
   - Monitor page generation time

**Deliverables**:
- Production wiki with Cargo integration
- All entities stored in Cargo
- All queries working
- Monitoring dashboard

**Success Criteria**:
- All pages render correctly
- All Cargo tables populated
- All queries return correct results
- No performance degradation

---

## Implementation Plan (Backlog - Not Recommended)

If Cargo is deferred to the backlog, the following design considerations must be implemented **now** to avoid rework later:

### Design Considerations (If Deferring)

1. **Template Parameter Names Must Match Cargo Fields**
   - Decision: Standardize template parameter naming now
   - Use lowercase with underscores (e.g., `drop_chance` not `dropChance`)
   - Document field name conventions in `CLAUDE.md`
   - **Rationale**: When adding Cargo later, field names must match template parameters. Changing parameter names requires regenerating all pages.

2. **Pydantic Context Models Must Be Cargo-Compatible**
   - Decision: Design context models to map cleanly to Cargo types
   - Avoid nested structures (Cargo doesn't support nested objects)
   - Use simple types: str, int, float, bool, list[str]
   - **Rationale**: Cargo tables mirror context models. Complex models require restructuring.

3. **Relationship Data Must Be Separate**
   - Decision: Output relationship data as separate blocks (not inline)
   - Example: Enemy drops as separate section, not inline in infobox
   - **Rationale**: Relationship data will become separate `#cargo_store` calls. Inline data can't be extracted easily.

4. **Template Structure Must Reserve Space for Cargo**
   - Decision: Use `<noinclude>` and `<includeonly>` sections in templates now
   - Reserve `<noinclude>` for future Cargo declarations
   - **Rationale**: Adding Cargo requires restructuring templates. Doing it now avoids template changes later.

5. **Field Names Must Be Documented**
   - Decision: Document all template parameters in schema files
   - Create `docs/template-schemas.md` mapping context models to template fields
   - **Rationale**: When designing Cargo schemas, we need clear field mappings. Without documentation, we'll have to reverse-engineer from code.

### When to Revisit

If deferring Cargo, revisit when:

1. **Wiki has 500+ pages**: Manual maintenance becomes unsustainable
2. **Users request dynamic lists**: "Show all level 10 items"
3. **Cross-references become error-prone**: Drop tables out of sync with item sources
4. **Manual editors struggle**: Adding new entity requires updating multiple pages

### Preconditions for Adding

Before adding Cargo to an existing wiki:

1. **Backup all pages**: Full export of wiki content
2. **Test on staging**: Clone wiki, install Cargo, test integration
3. **Freeze content**: Stop manual edits during migration
4. **Regenerate all pages**: Run full pipeline with Cargo templates
5. **Verify data**: Spot-check 100+ pages for accuracy
6. **Re-upload all pages**: Replace all pages with Cargo versions
7. **Recreate tables**: Run "Recreate data" on all templates
8. **Validate queries**: Test all Cargo queries
9. **Resume edits**: Re-enable manual editing

**Estimated Time**: 2-3 weeks (vs. 6 weeks for integrated approach)
**Risk**: High (potential data loss, broken pages, manual edit conflicts)

---

## Risks & Mitigation

### Risk 1: Cargo Extension Not Available

**Risk**: MediaWiki instance doesn't support Cargo extension

**Likelihood**: Low (Cargo is widely supported, well-documented)

**Impact**: High (blocks entire Cargo integration)

**Mitigation**:
- Verify Cargo availability before starting
- Test Cargo installation on dev wiki
- Fallback: Use Semantic MediaWiki (more complex, but similar functionality)

### Risk 2: Schema Changes Required

**Risk**: Cargo schema needs changes after deployment (field types, relationships)

**Likelihood**: Medium (schemas evolve as game updates)

**Impact**: High (requires recreating tables, regenerating pages)

**Mitigation**:
- Design schemas carefully upfront
- Review schemas with wiki team before deployment
- Version schemas (allow migrations)
- Use Cargo's "replacement table" feature for large updates (minimizes downtime)

### Risk 3: Performance Degradation

**Risk**: Cargo queries slow down page loads

**Likelihood**: Low (Cargo is optimized for gaming wikis)

**Impact**: Medium (poor user experience)

**Mitigation**:
- Test queries with full dataset before deployment
- Use Cargo indexes on frequently queried fields
- Cache query results where possible
- Limit query result sizes (pagination)

### Risk 4: Manual Edit Conflicts

**Risk**: Manual editors break Cargo storage with incorrect syntax

**Likelihood**: Medium (manual editing is error-prone)

**Impact**: Medium (missing data in Cargo tables, broken queries)

**Mitigation**:
- Provide clear editor documentation
- Use Page Forms extension (provides GUI for editing Cargo data)
- Validate Cargo storage in CI/CD pipeline
- Monitor Cargo tables for missing data

### Risk 5: Template Complexity

**Risk**: Templates become complex with Cargo calls, harder to maintain

**Likelihood**: Medium (Cargo adds lines of code)

**Impact**: Low (complexity is manageable)

**Mitigation**:
- Use template modules for Cargo call generation
- Keep Cargo logic separate from display logic
- Document template structure clearly
- Use consistent patterns across templates

---

## Recommendations

### Primary Recommendation: Implement Cargo Now

**Reasoning**:

1. **Minimal Overhead**: Our architecture supports Cargo with minimal changes (Jinja2 template updates only)
2. **Avoid Rework**: Adding Cargo later requires regenerating and re-uploading all pages
3. **User Expectation**: Modern gaming wikis have structured data and dynamic queries
4. **Maintainer Benefit**: Cargo simplifies manual editing and reduces maintenance burden
5. **Future-Proofing**: Many planned features depend on Cargo (dynamic lists, statistics, search)

**Implementation**: Follow 6-week phased rollout (see Implementation Plan above)

### Alternative Recommendation: Design for Cargo, Implement Later

**Only if**: Cargo installation is blocked (admin access, extension availability)

**Requirements**:
- Follow all "Design Considerations" above
- Document all template schemas now
- Use Cargo-compatible field names and types
- Reserve template structure for future Cargo integration

**Trade-offs**:
- Saves 6 weeks upfront
- Costs 2-3 weeks later (plus risk of data issues)
- Limits wiki functionality until Cargo is added

---

## Conclusion

MediaWiki Cargo is a **must-have** for the Erenshor wiki project. The extension provides structured data storage, dynamic queries, and automatic relationship tracking that are essential for gaming wikis.

**Key Findings**:

1. **Cargo integration is straightforward**: Our generator-based architecture already produces all necessary data. Adding Cargo requires only template updates (Jinja2 changes).

2. **Deferring Cargo creates technical debt**: Adding Cargo later requires regenerating and re-uploading all pages, plus schema design and template restructuring.

3. **Cargo benefits wiki maintainers**: Manual editors benefit from automatic cross-references, reducing maintenance burden.

4. **Cargo enables future features**: Dynamic lists, statistics, search, and filtering all depend on structured data.

**Recommendation**: **Implement Cargo now** as part of the current template generation refactor. Follow the 6-week phased rollout to minimize risk and ensure thorough testing.

**Next Steps**:

1. Review this document with wiki team
2. Confirm Cargo availability on wiki instance
3. Begin Phase 1: Install Cargo, design schemas, test with one template
4. Proceed with phased rollout per Implementation Plan

---

## Appendix: Useful Resources

### Official Documentation

- [Extension:Cargo](https://www.mediawiki.org/wiki/Extension:Cargo) - Main documentation
- [Extension:Cargo/Quick start guide](https://www.mediawiki.org/wiki/Extension:Cargo/Quick_start_guide) - Tutorial
- [Extension:Cargo/Storing data](https://www.mediawiki.org/wiki/Extension:Cargo/Storing_data) - Schema design
- [Extension:Cargo/Querying data](https://www.mediawiki.org/wiki/Extension:Cargo/Querying_data) - Query syntax
- [Extension:Cargo/Display formats](https://www.mediawiki.org/wiki/Extension:Cargo/Display_formats) - Output formatting

### Blog Posts

- [Representing one-to-many relations](https://river.me/blog/one-to-many/) - River Writes blog
- [List-type fields, for realsies](https://river.me/blog/cargo-list-type-fields/) - River Writes blog
- [One-to-many tables & #vardefine](https://river.me/blog/one-to-many-vardefine/) - River Writes blog

### Example Wikis Using Cargo

- Path of Exile Wiki (extensive Cargo usage with Lua)
- Leaguepedia (gaming wiki with complex Cargo queries)
- SORCERER Wiki (straightforward Cargo setup)
- Love and Deepspace Wiki (recent gaming wiki example)

### MediaWiki Extensions

- [Extension:Page Forms](https://www.mediawiki.org/wiki/Extension:Page_Forms) - GUI for editing Cargo data (strongly recommended)
- [Extension:Scribunto](https://www.mediawiki.org/wiki/Extension:Scribunto) - Lua integration for advanced Cargo queries
- [Extension:TemplateData](https://www.mediawiki.org/wiki/Extension:TemplateData) - Template documentation (useful for Cargo templates)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Author**: Claude Code (Anthropic)
**Status**: Ready for Review
