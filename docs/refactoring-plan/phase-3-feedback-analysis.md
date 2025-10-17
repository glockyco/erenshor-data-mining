# Phase 3 Feedback Analysis and Recommendations

**Date**: 2025-10-17
**Status**: Ready for Review
**Purpose**: Detailed analysis of user feedback on Phase 3 plan with concrete recommendations

---

## Executive Summary

This document analyzes critical user feedback on the Phase 3 plan and provides detailed recommendations for each issue. The feedback reveals significant gaps between the planned implementation and the actual requirements, particularly around:

1. **Backup System**: Current plan misunderstands the backup trigger (DB version vs game build)
2. **Item Page Templates**: Current plan underestimates complexity of different item types
3. **Manual Value Preservation**: Need more robust system to preserve wiki editor changes
4. **Conflict Detection/Resolution**: UX/DX needs thorough design before implementation
5. **Documentation Deferral**: Move to backlog to prioritize implementation work

**Key Findings**:
- Backup system needs complete redesign around game build IDs (not database changes)
- Item generation requires specialized templates for 7+ item types (weapon, armor, charm, aura, ability book, consumable, mold, general)
- Manual preservation needs automatic detection via MediaWiki `recentchanges` API
- Conflict resolution workflow needs clear user interaction design

**Recommended Action**: Update Phase 3 plan before beginning implementation.

---

## Issue 1: Backup System Architecture

### Current Understanding (From Phase 3 Plan)

**Task 1.2** says:
> "Automatic backups on database version changes"
> - Detect database changes (SHA256 hash)
> - Create backup before overwriting
> - Skip backup if database unchanged
> - Store backups in `.erenshor/backups/`

**Problem**: This is fundamentally wrong. Backups should be triggered by **game build changes**, not database changes.

### User's Requirements

From `phase-3-plan-feedback.md`:
> "I don't think the current plan matches what we discussed during our earlier planning sessions + discussions. As far as I remember, we want 1 update per game build. NOT 1 DB backup per "DB version" (we don't have a concept of DB versions in part of the project)! If we run extraction / export, multiple times on the same game version, old backups for this game build / version should simply be overwritten (DB, scripts, configs). If we have a new game build / version, we create a separate backup that does not overwrite the older ones for earlier builds / versions."

From `03-requirements-feedback.md`:
> "We want backups of C# scripts from the unity project and of the created SQLite DBs. One backup of each per build / version of the game. Since neither C# scripts nor SQLite DBs change within a single game build, we don't need to keep multiple per build. If we change the logic that creates the DB, outputs CAN change, so we need to preserve the most recent DB for the build."

**Key Points**:
1. 1 backup per **game build** (NOT per DB change)
2. Re-running export on same build → **overwrite** old backup
3. New game build → create **new** backup (don't overwrite)
4. Backup contents: DB + **game C# scripts** + configs
5. Created automatically during extraction/export

### Gap Analysis

Current plan is wrong in multiple ways:

| Current Plan | Actual Requirement | Impact |
|--------------|-------------------|---------|
| Trigger: DB SHA256 changes | Trigger: Game build ID changes | Wrong trigger entirely |
| One backup per DB change | One backup per game build | Too many backups |
| Backup DB only | Backup DB + game C# + configs | Missing critical files |
| Detect via hash comparison | Detect via Steam build ID | Wrong detection method |
| Store in generic directory | Organize by build ID | Poor organization |

### Proposed Solution

#### Architecture

**Backup Structure**:
```
.erenshor/backups/
├── main/
│   ├── build-20370413/              # One dir per game build ID
│   │   ├── metadata.json            # Backup metadata
│   │   ├── database.sqlite.gz       # Compressed database
│   │   ├── game-scripts.tar.gz      # Game C# scripts from Unity project
│   │   └── config.toml              # Config at time of backup
│   ├── build-20123456/
│   │   └── ...
│   └── latest -> build-20370413/    # Symlink to latest backup
├── playtest/
│   └── build-12345678/
│       └── ...
└── demo/
    └── build-98765432/
        └── ...
```

**Metadata Structure** (`metadata.json`):
```json
{
  "variant": "main",
  "app_id": "2382520",
  "build_id": "20370413",
  "created_at": "2025-10-17T15:30:00Z",
  "game_version": "1.0.5.3",
  "database_path": "database.sqlite.gz",
  "scripts_path": "game-scripts.tar.gz",
  "config_path": "config.toml",
  "files": {
    "database": {
      "size_bytes": 12345678,
      "sha256": "abc123..."
    },
    "scripts": {
      "size_bytes": 5678901,
      "sha256": "def456...",
      "file_count": 842
    }
  }
}
```

#### When Backups Are Created vs Overwritten

**Workflow**:
1. **Before export**: Get current game build ID from Steam manifest
2. **Check existing backups**: Look for backup dir for this build ID
3. **Decision**:
   - Build ID exists → **Overwrite** existing backup
   - Build ID new → **Create new** backup directory
4. **After export**: Create/update backup with latest DB and scripts

**Trigger Points**:
- `erenshor extract export` (after Unity export completes)
- `erenshor extract full` (after export step)
- NOT triggered by `download` or `rip` (no DB yet)

#### What Files Get Backed Up

**1. Database** (`database.sqlite.gz`):
- Source: `variants/{variant}/erenshor-{variant}.sqlite`
- Compressed with gzip
- Stores: All extracted game data

**2. Game C# Scripts** (`game-scripts.tar.gz`):
- Source: `variants/{variant}/unity/Assets/Scripts/` (game scripts, NOT our Editor scripts)
- Compressed tar archive
- Purpose: Track game code changes across versions
- Excludes: Our `Editor/` scripts (already in git)

**3. Config** (`config.toml`):
- Source: Current config at time of export
- Purpose: Know what settings were used for this backup
- Captures: Paths, Unity version, extraction settings

**NOT Backed Up**:
- Our editor scripts (`src/Assets/Editor/`) → already in git
- Downloaded game binaries → can re-download from Steam
- Unity project metadata → can regenerate with AssetRipper
- Logs → ephemeral debugging data

#### How Game Build Version Is Detected

**Steam Manifest**:
The `SteamCMD.get_build_id()` method already exists and reads from:
```
variants/{variant}/game/steamapps/appmanifest_{app_id}.acf
```

Example manifest content:
```
"AppState"
{
    "appid"     "2382520"
    "buildid"   "20370413"      <-- This is the game build ID
    "name"      "Erenshor"
    ...
}
```

**Implementation**:
```python
# In BackupService
def get_current_build_id(self, variant: str) -> str | None:
    """Get current game build ID for variant."""
    config = load_variant_config(variant)
    game_dir = Path(config["game_dir"])
    app_id = config["app_id"]

    steamcmd = SteamCMD()
    build_id = steamcmd.get_build_id(game_dir, app_id)

    if not build_id:
        logger.warning(f"Could not detect build ID for {variant}")
        return None

    return build_id

def should_create_backup(self, variant: str) -> tuple[bool, str | None]:
    """Check if backup should be created.

    Returns:
        (should_backup, build_id):
        - True if no backup exists for current build
        - False if backup exists (will be overwritten)
    """
    build_id = self.get_current_build_id(variant)
    if not build_id:
        logger.warning("Cannot create backup: build ID unknown")
        return False, None

    backup_dir = self.get_backup_dir(variant, build_id)
    exists = backup_dir.exists()

    if exists:
        logger.info(f"Backup exists for build {build_id}, will overwrite")
    else:
        logger.info(f"New build {build_id}, creating new backup")

    return True, build_id
```

#### Implementation Steps

**Step 1: Create BackupService class**
```python
# src/erenshor/application/services/backup.py

class BackupService:
    """Manage game build backups.

    Creates backups organized by game build ID. Each backup includes:
    - SQLite database (compressed)
    - Game C# scripts from Unity project (compressed)
    - Config file used for export

    Backups are per-variant and per-build. Re-running export on the same
    build overwrites the backup; new builds create new backups.
    """

    def __init__(self, backup_root: Path):
        """Initialize backup service.

        Args:
            backup_root: Root directory for all backups (.erenshor/backups/)
        """
        self.backup_root = backup_root
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        variant: str,
        database_path: Path,
        game_scripts_dir: Path,
        config_path: Path
    ) -> Path | None:
        """Create or update backup for current game build.

        Args:
            variant: Variant name (main, playtest, demo)
            database_path: Path to SQLite database
            game_scripts_dir: Path to game scripts in Unity project
            config_path: Path to config file

        Returns:
            Path to backup directory if successful, None if failed
        """
        build_id = self.get_current_build_id(variant)
        if not build_id:
            return None

        backup_dir = self.get_backup_dir(variant, build_id)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup database (compressed)
        self._backup_database(database_path, backup_dir / "database.sqlite.gz")

        # Backup game scripts (compressed tar)
        self._backup_scripts(game_scripts_dir, backup_dir / "game-scripts.tar.gz")

        # Backup config (copy)
        shutil.copy2(config_path, backup_dir / "config.toml")

        # Create metadata
        self._create_metadata(variant, build_id, backup_dir)

        # Update 'latest' symlink
        self._update_latest_symlink(variant, build_id)

        logger.info(f"Backup created: {backup_dir}")
        return backup_dir

    def get_backup_dir(self, variant: str, build_id: str) -> Path:
        """Get backup directory for variant and build ID."""
        return self.backup_root / variant / f"build-{build_id}"

    def list_backups(self, variant: str) -> list[dict]:
        """List all backups for variant with metadata."""
        variant_dir = self.backup_root / variant
        if not variant_dir.exists():
            return []

        backups = []
        for backup_dir in sorted(variant_dir.iterdir()):
            if backup_dir.is_dir() and backup_dir.name.startswith("build-"):
                metadata_file = backup_dir / "metadata.json"
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    backups.append(metadata)

        return backups
```

**Step 2: Integrate with extract export**
```python
# In extract.py command

def export_command(variant: str, ...):
    """Export game data to SQLite."""

    # Run Unity export
    unity.export_batch(variant)

    # Create backup AFTER export completes
    backup_service = BackupService(Path(".erenshor/backups"))
    config = load_variant_config(variant)

    backup_dir = backup_service.create_backup(
        variant=variant,
        database_path=Path(config["database"]),
        game_scripts_dir=Path(config["unity_project"]) / "Assets" / "Scripts",
        config_path=Path("config.toml")
    )

    if backup_dir:
        console.print(f"[green]✓[/green] Backup created: {backup_dir}")
    else:
        console.print("[yellow]⚠[/yellow] Backup skipped (build ID unknown)")
```

**Step 3: Add backup info to status command**
```python
# In info.py command

def status_command():
    """Show system status."""

    # ... existing status ...

    # Show backup info
    backup_service = BackupService(Path(".erenshor/backups"))
    for variant in ["main", "playtest", "demo"]:
        backups = backup_service.list_backups(variant)
        if backups:
            latest = backups[-1]
            console.print(f"  Latest backup: build {latest['build_id']} ({latest['created_at']})")
            console.print(f"  Total backups: {len(backups)}")

            # Calculate total size
            total_size = sum(
                b["files"]["database"]["size_bytes"] +
                b["files"]["scripts"]["size_bytes"]
                for b in backups
            )
            console.print(f"  Disk usage: {format_bytes(total_size)}")
```

### Edge Cases and Handling

**1. Build ID not detected**:
- Cause: Manifest missing, game not downloaded
- Handling: Skip backup, log warning, continue export
- User sees: Warning message but export succeeds

**2. Manual re-export on same build**:
- Cause: User runs `erenshor extract export` twice
- Handling: Overwrite existing backup
- User sees: Message "Updating backup for build {id}"

**3. Disk space full**:
- Cause: Backup directory grows too large
- Handling: Fail gracefully, show disk usage
- User action: Manual cleanup of old backups

**4. Scripts directory missing**:
- Cause: AssetRipper didn't extract scripts properly
- Handling: Skip scripts backup, backup DB only, log warning
- User sees: Warning but backup still created

**5. Failed export (Unity crashes)**:
- Cause: Unity batch mode fails
- Handling: NO backup created (export must succeed first)
- User sees: Error message, no backup

**6. Partial backup (one file fails)**:
- Cause: Permission error, corrupt file
- Handling: Delete partial backup, report error
- User sees: Error message, backup not created

### Example Workflow

**Scenario 1: First export on new build**
```bash
$ erenshor extract export
[info] Exporting game data...
[info] Unity export completed successfully
[info] Detecting game build ID...
[info] Found build: 20370413
[info] New build detected, creating backup...
[info] Compressing database (12.3 MB)...
[info] Archiving game scripts (842 files)...
[info] Backup created: .erenshor/backups/main/build-20370413/
[success] Export completed
```

**Scenario 2: Re-export on same build (fixed export bug)**
```bash
$ erenshor extract export
[info] Exporting game data...
[info] Unity export completed successfully
[info] Detecting game build ID...
[info] Found build: 20370413
[info] Backup exists for build 20370413, updating...
[info] Compressing database (12.3 MB)...
[info] Archiving game scripts (842 files)...
[info] Backup updated: .erenshor/backups/main/build-20370413/
[success] Export completed
```

**Scenario 3: New game version**
```bash
$ erenshor extract full
[info] Downloading game from Steam...
[info] Download completed
[info] Extracting Unity project...
[info] Extraction completed
[info] Exporting game data...
[info] Unity export completed successfully
[info] Detecting game build ID...
[info] Found build: 20456789 (new!)
[info] Creating backup for new build...
[info] Compressing database (14.1 MB)...
[info] Archiving game scripts (901 files)...
[info] Backup created: .erenshor/backups/main/build-20456789/
[success] Pipeline completed
```

### Code Snippets

**Key helper methods**:
```python
def _backup_database(self, source: Path, dest: Path) -> None:
    """Compress and backup database."""
    import gzip

    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)

    logger.debug(f"Database backed up: {dest}")

def _backup_scripts(self, source_dir: Path, dest: Path) -> None:
    """Create compressed tar archive of game scripts."""
    import tarfile

    if not source_dir.exists():
        logger.warning(f"Scripts directory not found: {source_dir}")
        return

    with tarfile.open(dest, "w:gz") as tar:
        tar.add(source_dir, arcname="Scripts")

    # Count files
    with tarfile.open(dest, "r:gz") as tar:
        file_count = len(tar.getmembers())

    logger.debug(f"Scripts backed up: {file_count} files, {dest}")

def _create_metadata(self, variant: str, build_id: str, backup_dir: Path) -> None:
    """Create metadata.json for backup."""
    config = load_variant_config(variant)

    metadata = {
        "variant": variant,
        "app_id": config["app_id"],
        "build_id": build_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "game_version": self._detect_game_version(variant),
        "files": {
            "database": {
                "size_bytes": (backup_dir / "database.sqlite.gz").stat().st_size,
                "sha256": self._sha256(backup_dir / "database.sqlite.gz")
            },
            "scripts": {
                "size_bytes": (backup_dir / "game-scripts.tar.gz").stat().st_size,
                "sha256": self._sha256(backup_dir / "game-scripts.tar.gz"),
                "file_count": self._count_tar_files(backup_dir / "game-scripts.tar.gz")
            }
        }
    }

    (backup_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
```

---

## Issue 2: Item Page Templates

### Survey of Item Types

From the legacy implementation (`legacy/erenshor/application/generators/items/`), there are **7 distinct item type generators**:

#### 1. Weapon Items (`weapon_armor.py` - weapons)
**Template**: `{{Weapon}}` or fancy table
**Characteristics**:
- Damage, DPS, attack speed
- Weapon type (TwoHandMelee, OneHandMelee, TwoHandBow, OneHandDagger, TwoHandStaff, Wand)
- Primary/secondary slot restrictions
- Class restrictions
- Fancy stats table for display

**Example**: "Iron Sword", "Wooden Bow", "Mage Staff"

#### 2. Armor Items (`weapon_armor.py` - armor)
**Template**: `{{Armor}}` or fancy table
**Characteristics**:
- Defense stats (armor, resistances)
- Slot (Head, Chest, Legs, Feet, Hands, etc.)
- Class restrictions
- Fancy stats table for display

**Example**: "Leather Helmet", "Iron Chestplate", "Cloth Robe"

#### 3. Charm Items (`charms.py`)
**Template**: `{{Fancy-charm}}`
**Characteristics**:
- Slot: Charm (special equipment slot)
- Stat bonuses (no armor/damage)
- Passive effects
- Usually has special abilities

**Example**: "Charm of Protection", "Lucky Charm"

#### 4. Aura Items (`auras.py`)
**Template**: `{{Auras}}` or `{{Item}}`
**Characteristics**:
- Slot: Aura (special slot)
- Provides aura buff effect
- Usually permanent/passive
- Special aura mechanics

**Example**: "Aura of Strength", "Regeneration Aura"

#### 5. Ability Books (`ability_books.py`)
**Template**: `{{Ability Books}}` or `{{Ability_Books}}`
**Characteristics**:
- Teaches spell or skill when used
- Consumable (disappears after use)
- Links to spell/skill page
- May have class restrictions

**Example**: "Spell Scroll: Fireball", "Skill Book: Mining"

#### 6. Consumable Items (`consumables.py`)
**Template**: `{{Consumable}}`
**Characteristics**:
- Disposable: true
- ItemEffectOnClick (healing, buffs, etc.)
- Usually stackable
- One-time use

**Example**: "Health Potion", "Mana Potion", "Food items"

#### 7. Mold Items (`molds.py`)
**Template**: `{{Mold}}`
**Characteristics**:
- Template flag = 1
- Used in crafting to create other items
- Not consumed in crafting
- Links to craftable items

**Example**: "Sword Mold", "Helmet Mold"

#### 8. General Items (`general.py`)
**Template**: `{{Item}}` (fallback)
**Characteristics**:
- Doesn't fit other categories
- Quest items, materials, misc items
- Basic item template

**Example**: "Quest Key", "Crafting Material", "Misc Item"

### Template Requirements

Each item type needs different template structure:

#### Weapons & Armor - Fancy Tables
**Special**: Use "Fancy" tables with visual stat bars
```wikitext
{{Fancy-weapon
|name=Iron Sword
|damage=50
|dps=25
|speed=2.0
|type=OneHandMelee
|class=Warrior, Knight
|...fancy table fields...
}}
```

**Requirements**:
- Complex stat calculations (DPS, effective values)
- Visual stat bars
- Class restriction formatting
- Source enrichment (vendors, drops, crafting)

#### Charms - Special Fields
```wikitext
{{Fancy-charm
|name=Charm of Protection
|effect=+10% Defense
|bonus=+5 Armor
|...
}}
```

**Requirements**:
- Stat bonus parsing
- Effect description formatting
- No damage/armor stats

#### Auras - Buff Effects
```wikitext
{{Auras
|name=Aura of Strength
|effect=+10 Strength to nearby allies
|radius=10m
|...
}}
```

**Requirements**:
- Aura effect parsing
- Radius/range information
- Buff mechanics

#### Ability Books - Spell/Skill Links
```wikitext
{{Ability Books
|name=Spell Scroll: Fireball
|teaches=[[Fireball]]
|level=10
|class=Mage
|...
}}
```

**Requirements**:
- Spell/skill link resolution
- Level requirements
- Class restrictions
- One-time use notation

#### Consumables - Effect Parsing
```wikitext
{{Consumable
|name=Health Potion
|effect=Restores 100 HP
|cooldown=30s
|stack=20
|...
}}
```

**Requirements**:
- ItemEffectOnClick parsing
- Cooldown formatting
- Stack size
- Disposable flag

#### Molds - Crafting Links
```wikitext
{{Mold
|name=Sword Mold
|creates=[[Iron Sword]], [[Steel Sword]]
|reusable=yes
|...
}}
```

**Requirements**:
- List of craftable items
- Reusable notation
- Crafting material links

#### General - Basic Template
```wikitext
{{Item
|name=Quest Key
|type=Quest Item
|description=Opens the ancient door
|...
}}
```

**Requirements**:
- Basic fields only
- Quest item notation
- Minimal complexity

### Old Architecture Analysis

**Legacy Structure** (`legacy/erenshor/application/generators/items/`):

```
items/
├── __init__.py              # ItemGenerator facade
├── base.py                  # classify_item_kind(), build_item_types()
├── weapon_armor.py          # WeaponArmorGenerator (both types!)
├── charms.py                # CharmGenerator
├── auras.py                 # AuraGenerator
├── ability_books.py         # AbilityBookGenerator
├── consumables.py           # ConsumableGenerator
├── molds.py                 # MoldGenerator
├── general.py               # GeneralItemGenerator
├── sources.py               # SourceEnricher (vendors, drops, crafting)
└── stats.py                 # Stat formatting utilities
```

**Pros**:
- ✅ Clear separation by item type
- ✅ Specialized logic per type
- ✅ Shared utilities (classify, sources)
- ✅ Facade pattern for orchestration

**Cons**:
- ❌ Weapon + Armor in same file (mixed concerns)
- ❌ Heavy coupling to legacy database ORM (SQLAlchemy)
- ❌ String-based template building (error-prone)
- ❌ No Jinja2 (hard to maintain templates)
- ❌ Source enrichment tightly coupled to generators
- ❌ No clear extension point for new entity types (quests, etc.)

**Key Insight**: The classification system (`classify_item_kind()`) is solid and should be preserved. The generator structure is good but needs modernization.

### Proposed Architecture

**Goals**:
1. Keep separation by item type (proven pattern)
2. Use Jinja2 templates (not string building)
3. Decouple source enrichment from generation
4. Support extension to non-item entities (quests, etc.)
5. Type-safe template rendering

**New Structure**:
```
src/erenshor/application/generators/
├── page_generator.py           # Main PageGenerator class
├── template_loader.py          # Jinja2 template loading
├── filters.py                  # Jinja2 custom filters
├── items/
│   ├── __init__.py             # Item generator exports
│   ├── classifier.py           # classify_item_kind() (from base.py)
│   ├── weapon_generator.py     # Weapon-specific logic
│   ├── armor_generator.py      # Armor-specific logic
│   ├── charm_generator.py      # Charm-specific logic
│   ├── aura_generator.py       # Aura-specific logic
│   ├── ability_book_generator.py
│   ├── consumable_generator.py
│   ├── mold_generator.py
│   └── general_generator.py
├── abilities/
│   ├── spell_generator.py      # Future: spell pages
│   └── skill_generator.py      # Future: skill pages
├── characters/
│   └── character_generator.py  # Future: NPC/enemy pages
└── quests/
    └── quest_generator.py      # Future: quest pages

templates/wiki/
├── items/
│   ├── weapon.j2               # {{Fancy-weapon}} template
│   ├── armor.j2                # {{Fancy-armor}} template
│   ├── charm.j2                # {{Fancy-charm}} template
│   ├── aura.j2                 # {{Auras}} template
│   ├── ability_book.j2         # {{Ability Books}} template
│   ├── consumable.j2           # {{Consumable}} template
│   ├── mold.j2                 # {{Mold}} template
│   └── general.j2              # {{Item}} template
├── abilities/
│   └── ability.j2              # Future: {{Ability}} template
├── characters/
│   └── character.j2            # Future: {{Enemy}} template
└── shared/
    ├── infobox_base.j2         # Shared infobox structure
    └── sources.j2              # Shared source formatting

```

**Key Classes**:

```python
# page_generator.py

class PageGenerator:
    """Generate wiki pages from database entities.

    Facade that delegates to specialized generators based on entity type.
    Uses Jinja2 templates for all rendering.
    """

    def __init__(self, template_dir: Path):
        self.template_env = self._setup_jinja2(template_dir)
        self.item_generators = self._setup_item_generators()

    def generate(
        self,
        entity: Entity,
        sources: SourceData,
        context: GenerationContext
    ) -> GeneratedPage:
        """Generate wiki page for entity.

        Args:
            entity: Domain entity (Item, Spell, Character, etc.)
            sources: Enriched source data (vendors, drops, etc.)
            context: Generation context (registry, linker, etc.)

        Returns:
            GeneratedPage with title, content, metadata
        """
        # Dispatch by entity type
        if isinstance(entity, Item):
            return self._generate_item(entity, sources, context)
        elif isinstance(entity, Spell):
            return self._generate_spell(entity, sources, context)
        # ... etc

    def _generate_item(
        self,
        item: Item,
        sources: SourceData,
        context: GenerationContext
    ) -> GeneratedPage:
        """Generate item page (delegates to specialized generators)."""
        from .items.classifier import classify_item_kind

        kind = classify_item_kind(item)
        generator = self.item_generators[kind]

        # Generator returns template name + data
        template_name, template_data = generator.prepare_data(
            item, sources, context
        )

        # Render template
        template = self.template_env.get_template(template_name)
        content = template.render(**template_data)

        return GeneratedPage(
            title=context.linker.resolve_item_title(item),
            content=content,
            entity_ref=EntityRef.from_item(item)
        )
```

```python
# items/weapon_generator.py

class WeaponGenerator:
    """Generate weapon item pages."""

    def prepare_data(
        self,
        item: Item,
        sources: SourceData,
        context: GenerationContext
    ) -> tuple[str, dict]:
        """Prepare template data for weapon.

        Returns:
            (template_name, template_data)
        """
        # Calculate weapon-specific stats
        damage = item.damage or 0
        attack_speed = item.attack_speed or 1.0
        dps = damage / attack_speed if attack_speed > 0 else 0

        # Build template data
        data = {
            "item": item,
            "name": item.name,
            "damage": damage,
            "dps": dps,
            "attack_speed": attack_speed,
            "weapon_type": item.weapon_type,
            "slot": item.required_slot,
            "classes": self._format_classes(item.classes),
            "sources": self._format_sources(sources),
            "stats": self._build_stat_table(item),
            # ... more fields
        }

        return "items/weapon.j2", data

    def _build_stat_table(self, item: Item) -> dict:
        """Build fancy stat table data."""
        # Complex logic for visual stat bars
        # ...
        return stats
```

**Template Example** (`templates/wiki/items/weapon.j2`):
```jinja2
{{Fancy-weapon
|name={{ name }}
|image={{ name }}.png
|damage={{ damage }}
|dps={{ dps|round(2) }}
|speed={{ attack_speed }}
|type={{ weapon_type }}
{% if classes %}
|class={{ classes|join(', ') }}
{% endif %}
|slot={{ slot }}

{# Sources section #}
{% if sources.vendors %}
|vendor={{ sources.vendors|format_sources }}
{% endif %}
{% if sources.drops %}
|drops={{ sources.drops|format_sources }}
{% endif %}
{% if sources.quests %}
|quests={{ sources.quests|format_sources }}
{% endif %}
{% if sources.crafting %}
|crafting={{ sources.crafting|format_sources }}
{% endif %}

{# Stats table #}
{% include 'shared/fancy_stats_table.j2' %}
}}

{# Manual section placeholder #}
== Description ==
<!-- MANUAL CONTENT PRESERVED -->

{# Additional info #}
{% if sources.related_quests %}
== Related Quests ==
{% for quest in sources.related_quests %}
* {{ quest }}
{% endfor %}
{% endif %}
```

### Implementation Plan

**Phase 1: Core Infrastructure** (Task 2.1-2.2)
1. Create `PageGenerator` class with Jinja2
2. Implement `classify_item_kind()` (port from legacy)
3. Create minimal templates for each item type
4. Add Jinja2 filters (format_number, format_percent, wiki_link)
5. Test with fixture entities

**Phase 2: Item Generators** (Task 2.2)
6. Implement `WeaponGenerator` (most complex)
7. Implement `ArmorGenerator` (similar to weapon)
8. Implement simple generators (Charm, Aura, Consumable, etc.)
9. Test each generator independently

**Phase 3: Source Enrichment** (Task 2.1)
10. Move source enrichment to separate service/queries
11. Integrate with generators via `SourceData` DTO
12. Test with real database

**Phase 4: Extension Points** (Future)
13. Add `SpellGenerator` structure (stub)
14. Add `CharacterGenerator` structure (stub)
15. Document how to add new entity types

**Incremental Approach**:
- Start with **General** items (simplest)
- Move to **Weapons** (most complex, proves architecture)
- Add other types incrementally
- Defer quest/character generators to future phases

### Key Decisions

**1. Separate generator per item type**
- Pro: Clear separation of concerns
- Pro: Easy to test independently
- Pro: Easy to extend
- Con: More files
- **Decision**: DO IT (proven pattern, worth the files)

**2. Jinja2 vs string building**
- Pro (Jinja2): Template syntax, easier to maintain
- Pro (Jinja2): Familiar to web developers
- Con (Jinja2): Learning curve
- **Decision**: Jinja2 (worth the investment)

**3. Weapon + Armor same generator?**
- Pro: Share fancy table logic
- Con: Mixed concerns
- **Decision**: SPLIT (easier to understand)

**4. Source enrichment location?**
- Option A: In generators (legacy approach)
- Option B: Separate service
- **Decision**: Separate (reusable, testable)

**5. Template inheritance?**
- Pro: DRY for common fields
- Con: Complexity, YAGNI
- **Decision**: NO inheritance (keep simple, use includes for shared parts)

---

## Issue 3: Manual Value Preservation

### Old Implementation Review

From `legacy/erenshor/application/transformers/merger.py`, the `FieldMerger` class preserves:

**Preserved Fields**:
```python
preserve_fields = ["othersource", "type", "imagecaption", "relatedquest"]
```

**Special Rules**:
1. **Weapon/Armor**: Do NOT preserve `type` or `imagecaption` (fancy tables handle these)
2. **Standard Items**: Preserve when our generated value is blank
3. **othersource**: Merge old + new values (deduplicate)

**How It Worked**:
1. Parse original page with mwparserfromhell
2. Extract existing template parameters
3. Parse generated infobox
4. For preserved fields:
   - If field exists in old page AND not blank
   - If field is blank in generated page OR preserve rule applies
   - Copy value from old to new
5. Special logic for `othersource`: merge both values

**Limitations**:
- ❌ Hardcoded field list (not extensible)
- ❌ Only preserves when generated value is blank
- ❌ No detection of manual overrides (assumes all old values are manual)
- ❌ No way to "un-override" if manual value is wrong
- ❌ No tracking of WHICH values were manually set

**Example**:
```wikitext
<!-- Original page (with manual edit) -->
{{Item
|name=Iron Sword
|othersource=Found in secret chest  <!-- MANUAL -->
|type=Legendary                      <!-- MANUAL -->
}}

<!-- Generated page -->
{{Item
|name=Iron Sword
|othersource=[[Mining]]              <!-- GENERATED -->
|type=                                <!-- GENERATED (blank) -->
}}

<!-- Merged result (legacy) -->
{{Item
|name=Iron Sword
|othersource=[[Mining]]<br>Found in secret chest  <!-- MERGED -->
|type=Legendary                                    <!-- PRESERVED -->
}}
```

### Proposed Automatic Detection System

**Goal**: Use MediaWiki's `recentchanges` API to automatically detect which template fields were manually edited by wiki users (not bots).

**Architecture**:

```python
# src/erenshor/application/services/manual_override_detector.py

class ManualOverrideDetector:
    """Detect manual overrides using MediaWiki recentchanges API.

    Tracks which template fields have been manually edited by humans
    (not bots) since the last automated update.
    """

    def __init__(self, wiki_client: MediaWikiClient):
        self.wiki_client = wiki_client
        self.bot_users = ["DataMinerBot"]  # Our bot username

    def detect_overrides(
        self,
        page_title: str,
        since: datetime
    ) -> dict[str, ManualOverride]:
        """Detect manual overrides for page.

        Args:
            page_title: Wiki page title
            since: Only check edits since this timestamp

        Returns:
            Dict mapping field names to ManualOverride objects
        """
        # Get recent changes for this page
        changes = self.wiki_client.get_recent_changes(
            page_title=page_title,
            start=since,
            end=datetime.now()
        )

        overrides = {}

        for change in changes:
            # Skip bot edits
            if change.user in self.bot_users:
                continue

            # Skip minor edits (optional)
            if change.minor:
                continue

            # Parse old and new revisions
            old_content = self.wiki_client.get_revision(change.old_revid)
            new_content = self.wiki_client.get_revision(change.new_revid)

            # Extract template changes
            field_changes = self._diff_template_fields(
                old_content, new_content
            )

            # Record as manual overrides
            for field, (old_val, new_val) in field_changes.items():
                overrides[field] = ManualOverride(
                    field=field,
                    old_value=old_val,
                    new_value=new_val,
                    changed_by=change.user,
                    changed_at=change.timestamp,
                    edit_comment=change.comment
                )

        return overrides

    def _diff_template_fields(
        self,
        old_content: str,
        new_content: str
    ) -> dict[str, tuple[str, str]]:
        """Compare template fields between revisions.

        Returns:
            Dict mapping field name to (old_value, new_value)
        """
        old_tpl = self._extract_infobox(old_content)
        new_tpl = self._extract_infobox(new_content)

        if not old_tpl or not new_tpl:
            return {}

        changes = {}

        # Check all fields in new template
        for field in new_tpl.keys():
            old_val = old_tpl.get(field, "").strip()
            new_val = new_tpl.get(field, "").strip()

            if old_val != new_val:
                changes[field] = (old_val, new_val)

        return changes

@dataclass
class ManualOverride:
    """Represents a manual edit to a template field."""
    field: str
    old_value: str
    new_value: str
    changed_by: str
    changed_at: datetime
    edit_comment: str

    def is_likely_correct(self) -> bool:
        """Heuristic: is this override likely correct?

        Checks:
        - Not a vandalism pattern
        - Edit comment suggests intentional change
        - Changed by trusted user (optional)
        """
        # Check for vandalism patterns
        if self.new_value.lower() in ["test", "asdf", "spam"]:
            return False

        # Check if cleared field (likely wrong)
        if self.old_value and not self.new_value:
            return False

        # Check edit comment for keywords
        positive_keywords = ["fix", "correct", "update", "add"]
        if any(kw in self.edit_comment.lower() for kw in positive_keywords):
            return True

        # Default: assume intentional
        return True
```

**MediaWiki API Integration**:
```python
# Add to MediaWikiClient

def get_recent_changes(
    self,
    page_title: str,
    start: datetime,
    end: datetime
) -> list[PageChange]:
    """Get recent changes for page using recentchanges API.

    Args:
        page_title: Page title
        start: Start timestamp
        end: End timestamp

    Returns:
        List of PageChange objects
    """
    params = {
        "action": "query",
        "list": "recentchanges",
        "rctitle": page_title,
        "rcstart": start.isoformat(),
        "rcend": end.isoformat(),
        "rcprop": "user|timestamp|comment|ids|flags",
        "rclimit": "500",
        "format": "json"
    }

    response = self._request("GET", params=params)
    changes = []

    for item in response.get("query", {}).get("recentchanges", []):
        changes.append(PageChange(
            revid=item["revid"],
            old_revid=item.get("old_revid"),
            user=item["user"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            comment=item.get("comment", ""),
            minor=item.get("minor", False)
        ))

    return changes

def get_revision(self, revid: int) -> str:
    """Get page content for specific revision ID."""
    params = {
        "action": "query",
        "revids": str(revid),
        "prop": "revisions",
        "rvprop": "content",
        "format": "json"
    }

    response = self._request("GET", params=params)
    pages = response.get("query", {}).get("pages", {})

    for page in pages.values():
        revisions = page.get("revisions", [])
        if revisions:
            return revisions[0].get("*", "")

    return ""
```

### Preservation Policy

**Rules for When to Preserve vs Override**:

#### Preserve Manual Changes IF:
1. ✅ Changed by human user (not bot)
2. ✅ Change happened since last bot update
3. ✅ Field is in preservation list
4. ✅ Override passes validation (`is_likely_correct()`)
5. ✅ New generated value differs from manual value

#### Override Manual Changes IF:
1. ❌ Changed by bot → ignore (not manual)
2. ❌ Vandalism detected → override (clear vandalism)
3. ❌ Field cleared → override (likely accidental)
4. ❌ User opts to force update → override (explicit choice)
5. ❌ Game data fundamentally changed → conflict (user decides)

**Preservation List** (fields to check):
```python
PRESERVABLE_FIELDS = [
    # Source info (often manually added)
    "othersource",
    "notes",
    "trivia",

    # Display info (sometimes manually corrected)
    "imagecaption",

    # Classification (sometimes manually corrected)
    "type",  # But NOT for weapon/armor (fancy tables)

    # Quest links (sometimes manually added)
    "relatedquest",

    # Strategy/usage info
    "usage",
    "strategy",
]
```

**Non-Preservable Fields** (always override):
```python
NON_PRESERVABLE_FIELDS = [
    # Core data (always from database)
    "name",
    "level",
    "damage",
    "armor",
    "stats",

    # Computed data
    "dps",
    "value",

    # Auto-generated sources
    "vendor",
    "drops",
    "crafting",
]
```

### Edge Cases and Solutions

**1. Conflicting Changes (Manual + Game Update)**:
```
Old DB:    name="Iron Sword", damage=50
Manual:    name="Iron Longsword"  (user renamed)
New DB:    name="Iron Sword", damage=75  (game buffed)
```
**Solution**: CONFLICT
- Cannot auto-merge (name changed in DB vs manual)
- Flag as conflict
- User must decide: keep manual name OR accept DB name

**2. Wrong Manual Edit (User Mistake)**:
```
Original:  type="Weapon"
Manual:    type="Waepon"  (typo)
Generated: type="Weapon"
```
**Solution**: OVERRIDE
- Validate manual value
- If nonsensical → override
- Log warning for review

**3. Outdated Manual Edit (Game Changed)**:
```
Manual:    othersource="Only drops from Boss X"
New DB:    Now also drops from Boss Y
Generated: othersource="[[Boss X]], [[Boss Y]]"
```
**Solution**: MERGE
- Manual: "Only drops from Boss X"
- Generated: "[[Boss X]], [[Boss Y]]"
- Result: "[[Boss X]], [[Boss Y]]<br>Only drops from Boss X" (note becomes outdated context)
- OR: CONFLICT (user decides if manual note still relevant)

**4. Vandalism Detection**:
```
Manual:    name="SPAM SPAM SPAM"
Generated: name="Iron Sword"
```
**Solution**: OVERRIDE
- Detect vandalism patterns
- Auto-override without conflict
- Log for admin review

**5. Mass Manual Changes (Wiki Editor Cleanup)**:
```
Editor changed imagecaption on 50 pages
All changes intentional and correct
```
**Solution**: PRESERVE ALL
- Detect change pattern
- Preserve all 50 changes
- Don't flag as conflict

**6. Bot vs Manual Race Condition**:
```
Time T+0: Bot updates page
Time T+1: User edits page
Time T+2: Bot updates page again
```
**Solution**: DETECT CONFLICT
- Check recentchanges since last bot edit
- If user edited after bot → conflict
- User must review changes

### UX/DX Design

**User Interaction Flow**:

```bash
# Step 1: Generate pages (detects conflicts)
$ erenshor wiki update

[info] Generating wiki pages...
[info] Checking for manual overrides...
[warn] Detected 3 pages with manual changes:
  - Iron Sword: field 'othersource' manually edited by WikiUser123
  - Health Potion: field 'imagecaption' manually edited by Editor456
  - Magic Amulet: field 'type' manually edited by Contributor789

[info] Generated pages saved to: .erenshor/wiki/generated/
[warn] 3 conflicts require review

# Step 2: Review conflicts
$ erenshor wiki conflicts

Conflicts Detected (3):

1. Iron Sword
   Field: othersource
   Current: "[[Mining]]"
   Manual: "Found in secret chest near spawn"
   Changed by: WikiUser123 on 2025-10-15
   Edit comment: "Added missing location info"

   Options:
   a) Keep manual value (preserve user's addition)
   b) Use generated value (override with data)
   c) Merge both values (recommended for sources)
   d) Skip this page (resolve later)

   Choice: c

   Result: "[[Mining]]<br>Found in secret chest near spawn"

2. Health Potion
   Field: imagecaption
   Current: (empty)
   Manual: "A red potion that restores health"
   Changed by: Editor456 on 2025-10-16
   Edit comment: "Added caption"

   Options:
   a) Keep manual value (preserve)
   b) Use generated value (empty)

   Choice: a

   Result: "A red potion that restores health" (preserved)

3. Magic Amulet
   Field: type
   Current: "Consumable"
   Manual: "Legendary Artifact"
   Changed by: Contributor789 on 2025-10-14
   Edit comment: (no comment)

   [warn] Generated type 'Consumable' differs significantly from manual 'Legendary Artifact'
   [warn] This may indicate a classification error

   Options:
   a) Keep manual value
   b) Use generated value
   c) Skip (needs investigation)

   Choice: c

   Result: Skipped (will not update this page)

[success] Conflict resolution complete
[info] Resolved: 2 pages
[info] Skipped: 1 page
[info] Merged pages saved to: .erenshor/wiki/merged/

# Step 3: Push to wiki (after conflicts resolved)
$ erenshor wiki push

[info] Pushing 247 pages to wiki...
[warn] Skipping 1 page with unresolved conflicts: Magic Amulet
[info] Pages pushed: 247
[info] Pages skipped: 1

[success] Wiki update complete
```

**Non-Interactive Mode** (for automation):
```bash
# Auto-preserve all manual changes (safest)
$ erenshor wiki update --preserve-manual

# Auto-override all manual changes (dangerous!)
$ erenshor wiki update --force-override

# Merge sources, preserve text, override stats (recommended)
$ erenshor wiki update --auto-resolve=smart
```

**Conflict Storage**:
```json
// .erenshor/wiki/conflicts.json
{
  "conflicts": [
    {
      "page_title": "Iron Sword",
      "field": "othersource",
      "current_value": "[[Mining]]",
      "manual_value": "Found in secret chest near spawn",
      "changed_by": "WikiUser123",
      "changed_at": "2025-10-15T14:30:00Z",
      "edit_comment": "Added missing location info",
      "resolution": "merge",
      "resolved_at": "2025-10-17T10:00:00Z",
      "resolved_value": "[[Mining]]<br>Found in secret chest near spawn"
    },
    {
      "page_title": "Magic Amulet",
      "field": "type",
      "current_value": "Consumable",
      "manual_value": "Legendary Artifact",
      "changed_by": "Contributor789",
      "changed_at": "2025-10-14T09:15:00Z",
      "edit_comment": "",
      "resolution": "skip",
      "resolved_at": null,
      "resolved_value": null
    }
  ]
}
```

### Implementation Approach

**Step 1: Add ManualOverrideDetector**
```python
# Task 2.3: Extend ContentMerger

class ContentMerger:
    def __init__(
        self,
        wiki_client: MediaWikiClient,
        detector: ManualOverrideDetector
    ):
        self.wiki_client = wiki_client
        self.detector = detector

    def merge(
        self,
        original: str,
        generated: str,
        page_title: str,
        last_update: datetime
    ) -> MergeResult:
        """Merge generated content with original page.

        Args:
            original: Original wiki page content
            generated: Generated page content
            page_title: Page title
            last_update: Timestamp of last bot update

        Returns:
            MergeResult with merged content + conflicts
        """
        # Detect manual overrides
        overrides = self.detector.detect_overrides(
            page_title, since=last_update
        )

        # Parse templates
        orig_tpl = self._extract_infobox(original)
        gen_tpl = self._extract_infobox(generated)

        # Build merged template
        merged_tpl = gen_tpl.copy()
        conflicts = []

        for field, override in overrides.items():
            # Check if field is preservable
            if field not in PRESERVABLE_FIELDS:
                continue

            # Get generated value
            gen_value = gen_tpl.get(field, "").strip()
            manual_value = override.new_value.strip()

            # Check if values differ
            if gen_value == manual_value:
                # No conflict (manual matches generated)
                continue

            # Decide: preserve, override, or conflict?
            if override.is_likely_correct():
                if field == "othersource":
                    # Merge sources
                    merged_tpl[field] = self._merge_sources(gen_value, manual_value)
                else:
                    # Preserve manual value
                    merged_tpl[field] = manual_value
            else:
                # Flag as conflict
                conflicts.append(Conflict(
                    page_title=page_title,
                    field=field,
                    current_value=gen_value,
                    manual_value=manual_value,
                    override=override
                ))

        # Render merged template
        merged_content = self._render_template(merged_tpl)

        return MergeResult(
            content=merged_content,
            conflicts=conflicts,
            preserved_fields=[
                f for f, o in overrides.items()
                if f in merged_tpl and merged_tpl[f] == o.new_value
            ]
        )
```

**Step 2: Conflict Resolution CLI**
```python
# Task 2.5: Add conflict resolution command

@wiki.command("conflicts")
def conflicts_command():
    """List and review conflicts from wiki update."""
    conflicts = load_conflicts()

    if not conflicts:
        console.print("[green]No conflicts![/green]")
        return

    console.print(f"[yellow]Conflicts Detected ({len(conflicts)})[/yellow]\n")

    for i, conflict in enumerate(conflicts, 1):
        console.print(f"{i}. {conflict.page_title}")
        console.print(f"   Field: {conflict.field}")
        console.print(f"   Current: {conflict.current_value}")
        console.print(f"   Manual: {conflict.manual_value}")
        console.print(f"   Changed by: {conflict.changed_by} on {conflict.changed_at}")
        console.print()

@wiki.command("resolve-conflict")
def resolve_conflict_command(page_title: str):
    """Interactively resolve conflict for page."""
    conflicts = load_conflicts()
    page_conflicts = [c for c in conflicts if c.page_title == page_title]

    if not page_conflicts:
        console.print(f"[red]No conflicts for page: {page_title}[/red]")
        return

    for conflict in page_conflicts:
        console.print(f"\nField: {conflict.field}")
        console.print(f"Current: {conflict.current_value}")
        console.print(f"Manual: {conflict.manual_value}")
        console.print()

        console.print("Options:")
        console.print("  a) Keep manual value (preserve)")
        console.print("  b) Use generated value (override)")
        if conflict.field == "othersource":
            console.print("  c) Merge both values (recommended for sources)")
        console.print("  d) Skip this page (resolve later)")

        choice = Prompt.ask("Choice", choices=["a", "b", "c", "d"])

        if choice == "a":
            conflict.resolution = "preserve"
            conflict.resolved_value = conflict.manual_value
        elif choice == "b":
            conflict.resolution = "override"
            conflict.resolved_value = conflict.current_value
        elif choice == "c":
            conflict.resolution = "merge"
            conflict.resolved_value = f"{conflict.current_value}<br>{conflict.manual_value}"
        elif choice == "d":
            conflict.resolution = "skip"
            conflict.resolved_value = None

        conflict.resolved_at = datetime.now()

    save_conflicts(conflicts)
    console.print("[green]Conflict resolved![/green]")
```

**Step 3: Track Last Bot Update**
```python
# Store timestamp of last bot update per page
# .erenshor/wiki/last_update.json
{
  "pages": {
    "Iron Sword": "2025-10-15T10:00:00Z",
    "Health Potion": "2025-10-14T15:30:00Z",
    ...
  }
}

# Update after successful push
def update_last_update_timestamp(page_title: str):
    timestamps = load_last_updates()
    timestamps["pages"][page_title] = datetime.now().isoformat()
    save_last_updates(timestamps)
```

---

## Issue 4: Conflict Detection and Resolution

### Earlier Planning Discussions

From earlier planning docs, conflict detection was briefly mentioned but not thoroughly designed. Need to create complete workflow from scratch.

### Conflict Types

**1. Manual Template Edit Conflict**:
- **Cause**: User edited template field, bot wants to update same field
- **Example**: User changes `othersource`, bot generates new value
- **Detection**: Compare manual edit time vs last bot update
- **Resolution**: Preserve, override, or merge

**2. Concurrent Edit Conflict**:
- **Cause**: Page changed on wiki between fetch and push
- **Example**: User edits page while bot is preparing update
- **Detection**: Compare revision IDs (page.revid changed)
- **Resolution**: Refetch and re-merge, or abort

**3. Structural Change Conflict**:
- **Cause**: User reorganized page structure, bot expects old structure
- **Example**: User moved template to different section
- **Detection**: Template not found in expected location
- **Resolution**: Manual review needed

**4. Data Mismatch Conflict**:
- **Cause**: Database data contradicts manual entry
- **Example**: DB says item is level 10, user wrote level 15
- **Detection**: Significant difference in core fields
- **Resolution**: Investigate (may indicate DB bug or manual error)

**5. Deleted Template Conflict**:
- **Cause**: User removed entire template, bot wants to add it back
- **Example**: User deleted infobox, bot generates new one
- **Detection**: Template missing in original page
- **Resolution**: User decision (restore template OR skip page)

### Detection Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Conflict Detection Flow                   │
└─────────────────────────────────────────────────────────────┘

1. FETCH PAGES
   ├─ Download current wiki pages
   ├─ Store revision IDs
   └─ Cache locally

2. GENERATE PAGES
   ├─ Query database
   ├─ Generate new content
   └─ Store generated pages

3. DETECT MANUAL CHANGES (per page)
   ├─ Check recentchanges since last bot update
   ├─ Filter for human edits (not bot)
   ├─ Extract template field changes
   └─ Build override list

4. MERGE CONTENT (per page)
   ├─ Parse original template
   ├─ Parse generated template
   ├─ For each override:
   │  ├─ Check if field preservable
   │  ├─ Check if values differ
   │  ├─ Validate override (not vandalism)
   │  └─ Decision:
   │     ├─ Auto-preserve (if safe)
   │     ├─ Auto-merge (for sources)
   │     └─ Flag conflict (if ambiguous)
   └─ Build merged template

5. SAVE CONFLICTS
   ├─ Write conflicts.json
   ├─ Store conflict metadata
   └─ Show conflict count

6. USER REVIEWS CONFLICTS
   ├─ Run: erenshor wiki conflicts
   ├─ Review each conflict
   └─ Choose resolution

7. APPLY RESOLUTIONS
   ├─ Update merged pages with resolutions
   └─ Mark conflicts as resolved

8. CONCURRENT EDIT CHECK (before push)
   ├─ Refetch page revision IDs
   ├─ Compare to cached revision IDs
   └─ If changed → ABORT (page edited during merge)

9. PUSH PAGES
   ├─ Upload merged pages
   ├─ Skip pages with unresolved conflicts
   └─ Update last_update timestamps
```

### Resolution UX

**CLI Commands**:

```bash
# View all conflicts
erenshor wiki conflicts

# View conflicts for specific page
erenshor wiki conflicts --page "Iron Sword"

# Resolve conflicts interactively
erenshor wiki resolve-conflict "Iron Sword"

# Resolve all conflicts with policy
erenshor wiki resolve-all --policy preserve  # Preserve all manual
erenshor wiki resolve-all --policy override  # Override all manual
erenshor wiki resolve-all --policy smart     # Smart merge (sources=merge, text=preserve, stats=override)

# Clear conflict cache (re-detect)
erenshor wiki conflicts --refresh
```

**Interactive Resolution** (example session):

```
$ erenshor wiki resolve-conflict "Iron Sword"

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Conflict: Iron Sword                               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Field: othersource

┌─ Current Value (Generated) ────────────────────────┐
│ [[Mining]]                                          │
└─────────────────────────────────────────────────────┘

┌─ Manual Value (User Edit) ─────────────────────────┐
│ Found in secret chest near spawn                    │
│                                                      │
│ Changed by: WikiUser123                             │
│ Date: 2025-10-15 14:30:00                          │
│ Comment: "Added missing location info"             │
└─────────────────────────────────────────────────────┘

Options:
  [p] Preserve manual value (keep user's addition)
  [o] Override with generated value (use database data)
  [m] Merge both values (recommended for sources)
  [s] Skip this field (resolve later)
  [?] Show more info

Your choice: m

┌─ Merged Result ────────────────────────────────────┐
│ [[Mining]]<br>Found in secret chest near spawn      │
└─────────────────────────────────────────────────────┘

Apply this resolution? [Y/n]: Y

[✓] Conflict resolved

─────────────────────────────────────────────────────

Next conflict? (1 remaining)
[Enter] Continue  [q] Quit

(continues to next conflict...)
```

**Rich UI Components**:
```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

def show_conflict(conflict: Conflict):
    """Display conflict in rich format."""
    console = Console()

    # Title panel
    console.print(Panel(
        f"[bold]Conflict: {conflict.page_title}[/bold]",
        border_style="yellow"
    ))

    # Field info
    console.print(f"\nField: [cyan]{conflict.field}[/cyan]\n")

    # Current value panel
    console.print(Panel(
        conflict.current_value,
        title="Current Value (Generated)",
        border_style="blue"
    ))

    # Manual value panel
    manual_info = f"{conflict.manual_value}\n\n"
    manual_info += f"Changed by: {conflict.changed_by}\n"
    manual_info += f"Date: {conflict.changed_at}\n"
    manual_info += f"Comment: \"{conflict.edit_comment}\""

    console.print(Panel(
        manual_info,
        title="Manual Value (User Edit)",
        border_style="green"
    ))

    # Options table
    table = Table(show_header=False)
    table.add_row("[p]", "Preserve manual value", "(keep user's addition)")
    table.add_row("[o]", "Override with generated", "(use database data)")
    table.add_row("[m]", "Merge both values", "(recommended for sources)")
    table.add_row("[s]", "Skip this field", "(resolve later)")
    table.add_row("[?]", "Show more info", "")

    console.print("\nOptions:")
    console.print(table)

    # Get choice
    choice = Prompt.ask(
        "\nYour choice",
        choices=["p", "o", "m", "s", "?"],
        default="m"
    )

    return choice
```

### Batch Operations

**Scenario**: 50 pages have conflicts, user needs efficient resolution.

**Solution: Smart Policies**

```bash
# Policy-based resolution
$ erenshor wiki resolve-all --policy smart

Applying smart resolution policy:
  - Sources (othersource, vendor, drops): MERGE
  - Text (imagecaption, notes, trivia): PRESERVE
  - Stats (damage, armor, level): OVERRIDE
  - Types (type, class): CHECK (need review)

Resolving conflicts...
[✓] Resolved 45 conflicts automatically
[!] 5 conflicts require manual review:
    - Magic Amulet (type: ambiguous)
    - Ancient Sword (imagecaption: generated value exists)
    - Rare Potion (othersource: merge conflict)
    - Legendary Helm (trivia: validation failed)
    - Quest Item (notes: flagged by user)

Run 'erenshor wiki conflicts' to review remaining conflicts
```

**Policy Definitions**:
```python
class ResolutionPolicy:
    """Define automatic resolution rules."""

    SMART = {
        "othersource": "merge",
        "vendor": "merge",
        "drops": "merge",
        "crafting": "merge",
        "imagecaption": "preserve",
        "notes": "preserve",
        "trivia": "preserve",
        "damage": "override",
        "armor": "override",
        "level": "override",
        "type": "check",  # Needs review
        "class": "check",
    }

    PRESERVE_ALL = {
        "*": "preserve"  # Wildcard
    }

    OVERRIDE_ALL = {
        "*": "override"
    }

    def resolve(
        self,
        field: str,
        conflict: Conflict
    ) -> str | None:
        """Apply policy to conflict.

        Returns:
            Resolution ("preserve", "override", "merge", or None if needs review)
        """
        rule = self.SMART.get(field, self.SMART.get("*"))

        if rule == "check":
            # Needs manual review
            return None

        if rule == "merge":
            # Merge values
            return self._merge_values(conflict)

        if rule == "preserve":
            return conflict.manual_value

        if rule == "override":
            return conflict.current_value

        return None
```

### Implementation Details

**Code Structure**:

```python
# src/erenshor/application/services/conflict_resolver.py

class ConflictResolver:
    """Resolve conflicts between manual and generated content."""

    def __init__(
        self,
        policy: ResolutionPolicy = ResolutionPolicy.SMART
    ):
        self.policy = policy

    def resolve_interactive(self, conflict: Conflict) -> Resolution:
        """Resolve conflict interactively with user."""
        choice = show_conflict(conflict)

        if choice == "p":
            return Resolution(
                action="preserve",
                value=conflict.manual_value,
                reason="User chose to preserve manual edit"
            )
        elif choice == "o":
            return Resolution(
                action="override",
                value=conflict.current_value,
                reason="User chose to override with generated value"
            )
        elif choice == "m":
            merged = self._merge_values(conflict)
            return Resolution(
                action="merge",
                value=merged,
                reason="User chose to merge both values"
            )
        elif choice == "s":
            return Resolution(
                action="skip",
                value=None,
                reason="User chose to skip (resolve later)"
            )

    def resolve_auto(self, conflict: Conflict) -> Resolution | None:
        """Attempt automatic resolution via policy.

        Returns:
            Resolution if auto-resolved, None if needs manual review
        """
        result = self.policy.resolve(conflict.field, conflict)

        if result is None:
            # Needs manual review
            return None

        return Resolution(
            action=self.policy.SMART.get(conflict.field),
            value=result,
            reason=f"Auto-resolved via {self.policy.__class__.__name__}"
        )

    def resolve_batch(
        self,
        conflicts: list[Conflict]
    ) -> tuple[list[Resolution], list[Conflict]]:
        """Resolve multiple conflicts.

        Returns:
            (resolved, unresolved)
        """
        resolved = []
        unresolved = []

        for conflict in conflicts:
            resolution = self.resolve_auto(conflict)
            if resolution:
                resolved.append(resolution)
            else:
                unresolved.append(conflict)

        return resolved, unresolved
```

---

## Issue 5: Documentation Deferral

### Updated Priorities

User feedback:
> "We move docs to the backlog. Perhaps we want to tackle some other backlog items before that. We'll think about that later."

**Recommendation**: Move Milestone 5 (Documentation) tasks to backlog.

**Rationale**:
- Focus Phase 3 on implementation (working features > documentation)
- Update CLAUDE.md incrementally as features are built
- Write user guides when features stabilize
- Defer formal documentation milestone until post-Phase 3

**Keep Minimal Documentation**:
- Docstrings in code (always)
- README updates (as features complete)
- CLAUDE.md updates (incremental, per milestone)

**Defer to Backlog**:
- ❌ Task 5.1: Update CLAUDE.md (comprehensive update)
- ❌ Task 5.2: Create User Guides (formal guides)
- ❌ Task 5.3: Phase 3 Completion Report

**Replace With**:
- ✅ Inline documentation as features are built
- ✅ Code comments for complex logic
- ✅ Commit messages explain changes
- ✅ Quick-start examples in README

---

## Recommendations for Phase 3 Plan Updates

### Changes Required

**Task 1.2 - Backup Service** (MAJOR REWRITE):
- ❌ Remove: "Detect database changes (SHA256 hash)"
- ✅ Add: "Detect game build ID changes via SteamCMD manifest"
- ✅ Add: "Backup game C# scripts from Unity project"
- ✅ Add: "Organize backups by variant and build ID"
- ✅ Add: "Overwrite backup if same build, create new if different build"

**Task 2.2 - Page Generator** (EXPAND):
- ✅ Add: "Create 7+ specialized item generators (weapon, armor, charm, aura, ability book, consumable, mold)"
- ✅ Add: "Implement item classifier from legacy code"
- ✅ Add: "Use Jinja2 templates (not string building)"
- ✅ Add: "Create separate template per item type"

**Task 2.3 - Content Merger** (MAJOR EXPANSION):
- ✅ Add: "Integrate ManualOverrideDetector using MediaWiki recentchanges API"
- ✅ Add: "Implement preservation policy for different field types"
- ✅ Add: "Track last bot update timestamps per page"
- ✅ Add: "Validate manual overrides (detect vandalism)"
- ✅ Add: "Generate conflicts.json for unresolved conflicts"

**Task 2.5 - Wiki Commands** (ADD CONFLICT COMMANDS):
- ✅ Add: "Implement `wiki conflicts` command to list conflicts"
- ✅ Add: "Implement `wiki resolve-conflict <page>` for interactive resolution"
- ✅ Add: "Implement `wiki resolve-all --policy <policy>` for batch resolution"
- ✅ Add: "Add `--preserve-manual`, `--force-override`, `--auto-resolve` flags"

**Milestone 5 - Documentation** (DEFER):
- ❌ Move Task 5.1, 5.2, 5.3 to backlog
- ✅ Keep minimal inline documentation
- ✅ Update README incrementally

### New Tasks

**NEW Task 1.2a - Build ID Detection**:
- Implement `get_current_build_id()` in BackupService
- Test with all variants (main, playtest, demo)
- Handle missing manifest gracefully
- Estimated: 30 minutes

**NEW Task 2.2a - Item Classification**:
- Port `classify_item_kind()` from legacy code
- Add tests for all item types
- Document classification rules
- Estimated: 45 minutes

**NEW Task 2.3a - Manual Override Detection**:
- Implement `ManualOverrideDetector` class
- Integrate MediaWiki `recentchanges` API
- Add revision diffing logic
- Create override validation rules
- Estimated: 3 hours

**NEW Task 2.3b - Conflict Storage**:
- Create `conflicts.json` schema
- Implement conflict save/load
- Add conflict metadata tracking
- Estimated: 45 minutes

**NEW Task 2.5a - Conflict Resolution CLI**:
- Implement `wiki conflicts` command
- Implement `wiki resolve-conflict` command
- Add Rich UI for conflict display
- Create interactive resolution flow
- Estimated: 2.5 hours

### Task Reordering

**Original Order**:
1. Milestone 1 (CLI Orchestration)
2. Milestone 2 (Wiki Generation)
3. Milestone 3 (Sheets Deployment)
4. Milestone 4 (Integration Testing)
5. Milestone 5 (Documentation)

**Updated Order**:
1. Milestone 1 (CLI Orchestration) - UPDATED with build ID logic
2. Milestone 2 (Wiki Generation) - EXPANDED with conflict resolution
3. Milestone 3 (Sheets Deployment) - NO CHANGES
4. Milestone 4 (Integration Testing) - ADD conflict resolution tests
5. ~~Milestone 5 (Documentation)~~ - MOVED TO BACKLOG

**Dependencies Change**:
- Task 2.3 (Content Merger) now depends on NEW Task 2.3a (Override Detection)
- Task 2.5 (Wiki Commands) now depends on NEW Task 2.5a (Conflict Resolution)
- Task 4.2 (Service Tests) must include conflict resolution testing

---

## Open Questions

These questions need user input before finalizing Phase 3 plan:

### Question 1: Backup Retention Policy
**Question**: How long should we keep backups? Should there be a max count or max age?

**Options**:
- A) Keep all backups forever (manual cleanup only)
- B) Keep last N builds per variant (e.g., last 10 builds)
- C) Keep builds from last N days (e.g., last 90 days)
- D) Combination (e.g., keep all from last 30 days, then last 5 per variant)

**Recommendation**: Option A (keep all, manual cleanup) - disk space is cheap, historical data is valuable.

### Question 2: Conflict Resolution Default Policy
**Question**: What should be the default conflict resolution policy?

**Options**:
- A) Always preserve manual changes (safest)
- B) Always override with generated data (most up-to-date)
- C) Smart policy (merge sources, preserve text, override stats)
- D) Always require user review (no auto-resolution)

**Recommendation**: Option C (smart policy) - balances safety with automation.

### Question 3: Vandalism Detection Strictness
**Question**: How strict should vandalism detection be?

**Options**:
- A) Strict (auto-override anything suspicious)
- B) Moderate (flag suspicious, let user decide)
- C) Lenient (trust all edits unless clearly vandalism)

**Recommendation**: Option B (moderate) - flag suspicious edits for review.

### Question 4: Concurrent Edit Handling
**Question**: What to do if page is edited between fetch and push?

**Options**:
- A) Abort entirely (user must re-run)
- B) Refetch and re-merge automatically
- C) Push anyway with warning
- D) Skip page and continue with others

**Recommendation**: Option D (skip page, continue) - most resilient.

### Question 5: Item Type Template Priority
**Question**: Which item types should we implement first in Phase 3?

**Options**:
- A) All types in Phase 3 (comprehensive)
- B) Start with weapon/armor (most complex)
- C) Start with general (simplest)
- D) Start with consumables (most common)

**Recommendation**: Option C then B (general → weapon/armor → others) - prove architecture with simple, then tackle complex.

---

## Next Steps

1. **User Review**:
   - Review this analysis document
   - Answer open questions
   - Approve recommendations
   - Request any clarifications

2. **Update Phase 3 Plan**:
   - Rewrite Task 1.2 (Backup Service)
   - Expand Task 2.2 (Page Generator)
   - Expand Task 2.3 (Content Merger)
   - Add new tasks (2.2a, 2.3a, 2.3b, 2.5a)
   - Update estimates (will increase total time)
   - Defer Milestone 5 to backlog

3. **Update Task Dependencies**:
   - Add new dependency chains
   - Update milestone estimates
   - Revise timeline

4. **Begin Implementation**:
   - Start with Milestone 1 (updated backup system)
   - Move to Milestone 2 (expanded wiki generation)
   - Proceed with updated plan

---

**End of Analysis**
