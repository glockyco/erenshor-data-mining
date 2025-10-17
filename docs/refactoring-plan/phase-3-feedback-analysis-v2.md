# Phase 3 Feedback Analysis v2 (Second Round)

**Date**: 2025-10-17
**Status**: Ready for Review
**Purpose**: Updated analysis incorporating second round of user feedback with significant simplifications

---

## Executive Summary

This document addresses the second round of user feedback on Phase 3, with major simplifications and feature removal:

**Key Changes from V1**:
1. **Removed**: Zipped backups → use uncompressed directories for easy diffs
2. **Removed**: Automatic vandalism detection → manual configuration only
3. **Removed**: Complex merge strategies → simple preserve/override with custom resolvers
4. **Removed**: Most legacy templates → only {{Item}}, {{Fancy-Weapon}}, {{Fancy-Armor}}, {{Fancy-charm}}
5. **Added**: Precondition checks before all destructive operations (fail fast principle)
6. **Added**: Manual edit notification system (detect but don't auto-preserve)
7. **Simplified**: Template architecture using composition over inheritance

**Philosophy**: Cut complexity, fail fast, use configuration over code, focus on essentials.

---

## Changes from V1 Analysis

### What Was Removed

1. **Zipped Backups**
   - Removed: gzip compression of database
   - Removed: tar.gz of game scripts
   - Reason: Need easy diffs, not restoration

2. **Automatic Vandalism Detection**
   - Removed: Heuristic-based vandalism checking
   - Removed: Automatic override of "suspicious" edits
   - Removed: Complex validation logic
   - Reason: Feature creep, too brittle, wiki hasn't seen vandalism

3. **Complex Merge Strategies**
   - Removed: Automatic detection of "safe" vs "unsafe" manual edits
   - Removed: Multi-way merge logic
   - Removed: Conflict classification system
   - Reason: Too complex, prefer explicit configuration

4. **Legacy Templates**
   - Removed: {{Consumable}} template → use {{Item}} instead
   - Removed: {{Weapon}} template → use {{Item}} + {{Fancy-weapon}} table
   - Removed: {{Armor}} template → use {{Item}} + {{Fancy-armor}} table
   - Removed: {{Mold}} template → use {{Item}}
   - Removed: {{Ability Books}} / {{Ability_Books}} → use {{Item}}
   - Removed: {{Auras}} template → use {{Item}}
   - Reason: Discontinued in favor of simpler composition

5. **Concurrent Edit Detection on Upload**
   - Removed: Revision ID checking before push
   - Removed: Refetch-and-retry logic
   - Reason: Rate limiting concerns, fetch→update→push is fast anyway

### What Was Simplified

1. **Field Preservation**
   - Old: Automatic detection via recentchanges
   - New: Manual configuration + optional notification
   - Benefit: Predictable, no surprises

2. **Conflict Resolution**
   - Old: Auto-merge with smart policies
   - New: Keep old OR replace (no merging)
   - Exception: Custom resolution strategies per field
   - Benefit: Simpler logic, explicit behavior

3. **Template Architecture**
   - Old: Template inheritance hierarchy
   - New: Composition with reusable components
   - Benefit: Easier to understand and maintain

4. **Backup Space Management**
   - Old: Automatic retention policies
   - New: Keep all, show space usage on create
   - Benefit: Simple, transparent, user decides when to clean

### What Was Added

1. **Precondition Checks**
   - Check database exists before deploy
   - Check game downloaded before extract
   - Check Unity project exists before export
   - Fail fast before destructive operations

2. **Manual Edit Notifications**
   - Detect edits via recentchanges (notification only)
   - List pages needing review after update
   - Local review before pushing to wiki
   - No automatic preservation

3. **Custom Resolution Strategies**
   - Per-field resolution logic
   - Configurable via TOML
   - Examples: "preserve", "override", "merge_sources", "custom_handler"

4. **Uncompressed Backups**
   - Plain directory structure
   - Raw SQLite file
   - Raw C# script files
   - Easy to diff and browse

---

## Issue 1: Fail Fast and Precondition Checks

### Requirements

From feedback:
> "Following our 'fail fast' principle, we should abort any pipeline runs if any of the critical export steps failed. To ensure that separate individual command execution behaves properly, we should also add checks to each command that run BEFORE the actual command logic and check whether all necessary data / files / etc. is available (similar to our doctor commands, or perhaps we can even reuse them?)."

> "There should NOT be any partial backups - instead, the command should FAIL fast and loud before performing any potentially destructive operations if some requirements / preconditions for successful operation are not satisfied."

**Key Points**:
1. Abort pipeline if critical steps fail
2. Precondition checks BEFORE command logic
3. Similar to doctor commands (reuse if possible)
4. NO partial backups - atomic operations only
5. Fail fast and loud before destructive ops

### Proposed Design

#### Precondition System Architecture

**Core Concept**: Every command that performs potentially destructive operations or depends on prior pipeline state MUST check preconditions before executing.

**Reuse Doctor Commands**: YES - doctor commands already implement health checks. We can:
1. Extract check logic into reusable functions
2. Call these checks from commands as preconditions
3. Add new checks as needed for specific command requirements

**Structure**:
```python
# src/erenshor/application/services/preconditions.py

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

@dataclass
class PreconditionResult:
    """Result of a precondition check."""
    passed: bool
    message: str
    detail: str = ""

class PreconditionChecker:
    """Reusable precondition checks for commands.

    Extracts and reuses logic from doctor commands to provide
    fail-fast validation before destructive operations.
    """

    def __init__(self, variant: str):
        self.variant = variant
        self.config = load_variant_config(variant)

    # Core filesystem checks
    def check_game_downloaded(self) -> PreconditionResult:
        """Check if game files exist for variant."""
        game_dir = Path(self.config["game_dir"])
        manifest = game_dir / "steamapps" / f"appmanifest_{self.config['app_id']}.acf"

        if not game_dir.exists():
            return PreconditionResult(
                passed=False,
                message="Game not downloaded",
                detail=f"Game directory missing: {game_dir}"
            )

        if not manifest.exists():
            return PreconditionResult(
                passed=False,
                message="Game manifest missing",
                detail=f"Steam manifest not found: {manifest}"
            )

        return PreconditionResult(passed=True, message="Game downloaded")

    def check_unity_project_exists(self) -> PreconditionResult:
        """Check if Unity project exists and is valid."""
        unity_dir = Path(self.config["unity_project"])
        assets_dir = unity_dir / "Assets"

        if not unity_dir.exists():
            return PreconditionResult(
                passed=False,
                message="Unity project missing",
                detail=f"Unity project directory not found: {unity_dir}"
            )

        if not assets_dir.exists():
            return PreconditionResult(
                passed=False,
                message="Unity project invalid",
                detail=f"Assets directory missing: {assets_dir}"
            )

        return PreconditionResult(passed=True, message="Unity project exists")

    def check_database_exists(self) -> PreconditionResult:
        """Check if SQLite database exists and is valid."""
        db_path = Path(self.config["database"])

        if not db_path.exists():
            return PreconditionResult(
                passed=False,
                message="Database not found",
                detail=f"SQLite database missing: {db_path}"
            )

        # Check if file is valid SQLite
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cursor.fetchone()
            conn.close()
        except Exception as e:
            return PreconditionResult(
                passed=False,
                message="Database invalid",
                detail=f"SQLite database corrupted: {e}"
            )

        return PreconditionResult(passed=True, message="Database exists")

    def check_database_not_empty(self) -> PreconditionResult:
        """Check if database has data."""
        result = self.check_database_exists()
        if not result.passed:
            return result

        db_path = Path(self.config["database"])
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check for items table (core table)
        cursor.execute("SELECT COUNT(*) FROM Item")
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            return PreconditionResult(
                passed=False,
                message="Database empty",
                detail="Database exists but contains no items"
            )

        return PreconditionResult(
            passed=True,
            message=f"Database contains {count} items"
        )

    def check_editor_scripts_linked(self) -> PreconditionResult:
        """Check if Editor scripts are symlinked."""
        unity_dir = Path(self.config["unity_project"])
        editor_dir = unity_dir / "Assets" / "Editor"

        if not editor_dir.exists():
            return PreconditionResult(
                passed=False,
                message="Editor scripts not linked",
                detail=f"Editor directory missing: {editor_dir}"
            )

        # Check if it's a symlink
        if not editor_dir.is_symlink():
            return PreconditionResult(
                passed=False,
                message="Editor directory not a symlink",
                detail=f"Expected symlink, found regular directory: {editor_dir}"
            )

        # Check symlink target
        target = editor_dir.resolve()
        expected = Path("src/Assets/Editor").resolve()

        if target != expected:
            return PreconditionResult(
                passed=False,
                message="Editor symlink points to wrong location",
                detail=f"Expected: {expected}, Found: {target}"
            )

        return PreconditionResult(passed=True, message="Editor scripts linked")

    def check_unity_executable(self) -> PreconditionResult:
        """Check if Unity executable exists."""
        unity_path = Path(self.config.get("unity", {}).get("path", ""))

        if not unity_path or not Path(unity_path).exists():
            return PreconditionResult(
                passed=False,
                message="Unity executable not found",
                detail=f"Unity path invalid: {unity_path}"
            )

        return PreconditionResult(passed=True, message="Unity executable found")

    def check_all(
        self,
        checks: list[Callable[[], PreconditionResult]]
    ) -> tuple[bool, list[PreconditionResult]]:
        """Run multiple checks and return combined result.

        Args:
            checks: List of check methods to run

        Returns:
            (all_passed, results)
        """
        results = [check() for check in checks]
        all_passed = all(r.passed for r in results)
        return all_passed, results
```

#### Integration with Commands

**Pattern for Each Command**:
1. Define required preconditions
2. Check preconditions BEFORE any operations
3. Fail fast if any precondition fails
4. Only proceed if ALL preconditions pass

**Example: Extract Command**
```python
# cli/commands/extract.py

def command_main():
    """Extract Unity project and export to SQLite."""
    variant = get_variant_from_args()

    # PRECONDITION CHECKS
    checker = PreconditionChecker(variant)
    all_passed, results = checker.check_all([
        checker.check_game_downloaded,
        checker.check_unity_executable,
    ])

    if not all_passed:
        log_error("Precondition checks failed:")
        for result in results:
            if not result.passed:
                log_error(f"  ✗ {result.message}")
                if result.detail:
                    log_error(f"    {result.detail}")
        log_error("\nAbort: Fix issues before running extract")
        return 1

    # All checks passed - proceed with extraction
    log_info("Precondition checks passed")

    # ... rest of command logic ...
```

**Example: Export Command**
```python
# cli/commands/export.py

def command_main():
    """Export game data to SQLite via Unity batch mode."""
    variant = get_variant_from_args()

    # PRECONDITION CHECKS
    checker = PreconditionChecker(variant)
    all_passed, results = checker.check_all([
        checker.check_unity_project_exists,
        checker.check_editor_scripts_linked,
        checker.check_unity_executable,
    ])

    if not all_passed:
        log_error("Precondition checks failed:")
        for result in results:
            if not result.passed:
                log_error(f"  ✗ {result.message}")
                if result.detail:
                    log_error(f"    {result.detail}")
        log_error("\nAbort: Fix issues before running export")
        return 1

    # All checks passed - proceed with export
    log_info("Precondition checks passed")

    # ... rest of command logic ...
```

**Example: Deploy Command**
```python
# cli/commands/deploy.py (or wiki update)

def command_main():
    """Deploy data to wiki."""
    variant = get_variant_from_args()

    # PRECONDITION CHECKS
    checker = PreconditionChecker(variant)
    all_passed, results = checker.check_all([
        checker.check_database_exists,
        checker.check_database_not_empty,
    ])

    if not all_passed:
        log_error("Precondition checks failed:")
        for result in results:
            if not result.passed:
                log_error(f"  ✗ {result.message}")
                if result.detail:
                    log_error(f"    {result.detail}")
        log_error("\nAbort: Fix issues before deploying")
        return 1

    # All checks passed - proceed with deployment
    log_info("Precondition checks passed")

    # ... rest of command logic ...
```

#### Atomic Backup Operations

**Problem**: Avoid partial backups if operation fails mid-way.

**Solution**: Use temporary directory + atomic rename.

```python
# src/erenshor/application/services/backup.py

class BackupService:
    def create_backup(
        self,
        variant: str,
        database_path: Path,
        game_scripts_dir: Path,
        config_path: Path
    ) -> Path | None:
        """Create or update backup for current game build.

        Uses atomic operations to prevent partial backups.
        """
        # Get build ID
        build_id = self.get_current_build_id(variant)
        if not build_id:
            logger.error("Cannot create backup: build ID unknown")
            return None

        # Final backup location
        backup_dir = self.get_backup_dir(variant, build_id)

        # Temporary location (atomic operation)
        temp_dir = backup_dir.with_suffix(".tmp")

        try:
            # Clean up any existing temp dir
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

            # Create temp directory
            temp_dir.mkdir(parents=True, exist_ok=True)

            # PRECONDITION: Check all source files exist
            if not database_path.exists():
                raise FileNotFoundError(f"Database not found: {database_path}")
            if not game_scripts_dir.exists():
                raise FileNotFoundError(f"Game scripts not found: {game_scripts_dir}")
            if not config_path.exists():
                raise FileNotFoundError(f"Config not found: {config_path}")

            # Copy files to temp directory
            logger.info("Backing up database...")
            shutil.copy2(database_path, temp_dir / "database.sqlite")

            logger.info("Backing up game scripts...")
            shutil.copytree(
                game_scripts_dir,
                temp_dir / "game-scripts",
                dirs_exist_ok=True
            )

            logger.info("Backing up config...")
            shutil.copy2(config_path, temp_dir / "config.toml")

            # Create metadata
            logger.info("Creating metadata...")
            self._create_metadata(variant, build_id, temp_dir)

            # ATOMIC RENAME: temp -> final
            # This is atomic on most filesystems
            if backup_dir.exists():
                # Remove old backup first
                shutil.rmtree(backup_dir)

            temp_dir.rename(backup_dir)

            logger.info(f"Backup created: {backup_dir}")
            return backup_dir

        except Exception as e:
            # Clean up temp directory on failure
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            logger.error(f"Backup failed: {e}")
            return None
```

#### Reusing Doctor Command Logic

**Extract Checks from Doctor**:
```python
# cli/lib/modules/health.sh or similar

# Health check functions (can be called from doctor OR as preconditions)

check_game_downloaded() {
    local variant="$1"
    local game_dir=$(config_get "variants.${variant}.game_dir")
    local app_id=$(config_get "variants.${variant}.app_id")

    if [[ ! -d "$game_dir" ]]; then
        echo "FAIL: Game directory not found: $game_dir"
        return 1
    fi

    local manifest="$game_dir/steamapps/appmanifest_${app_id}.acf"
    if [[ ! -f "$manifest" ]]; then
        echo "FAIL: Steam manifest missing: $manifest"
        return 1
    fi

    echo "PASS: Game downloaded"
    return 0
}

check_unity_project() {
    local variant="$1"
    local unity_dir=$(config_get "variants.${variant}.unity_project")

    if [[ ! -d "$unity_dir" ]]; then
        echo "FAIL: Unity project not found: $unity_dir"
        return 1
    fi

    if [[ ! -d "$unity_dir/Assets" ]]; then
        echo "FAIL: Unity Assets directory missing"
        return 1
    fi

    echo "PASS: Unity project exists"
    return 0
}

check_database() {
    local variant="$1"
    local db_path=$(config_get "variants.${variant}.database")

    if [[ ! -f "$db_path" ]]; then
        echo "FAIL: Database not found: $db_path"
        return 1
    fi

    # Quick SQLite integrity check
    if ! sqlite3 "$db_path" "PRAGMA integrity_check;" >/dev/null 2>&1; then
        echo "FAIL: Database corrupted"
        return 1
    fi

    echo "PASS: Database exists and valid"
    return 0
}

# Precondition runner
run_preconditions() {
    local variant="$1"
    shift
    local checks=("$@")

    local all_passed=true

    for check in "${checks[@]}"; do
        if ! "$check" "$variant"; then
            all_passed=false
        fi
    done

    if [[ "$all_passed" == "false" ]]; then
        log_error "Precondition checks failed - aborting"
        return 1
    fi

    log_info "All precondition checks passed"
    return 0
}
```

**Use in Commands**:
```bash
# cli/commands/export.sh

command_main() {
    local variant="${1:-main}"

    # RUN PRECONDITIONS
    run_preconditions "$variant" \
        check_unity_project \
        check_editor_scripts_linked \
        check_unity_executable \
        || return 1

    # Proceed with export
    log_info "Starting Unity export..."
    # ... rest of export logic ...
}
```

### Implementation Details

**Task Breakdown**:
1. Create `PreconditionChecker` class (Python)
2. Extract health check functions from doctor (Bash)
3. Add precondition calls to each command
4. Update `BackupService` for atomic operations
5. Add tests for precondition logic

**Estimated Time**: 2-3 hours

### Example Workflows

**Scenario 1: User runs export without downloading game**
```bash
$ erenshor export

Precondition checks:
  ✗ Game not downloaded
    Game directory missing: /Users/.../variants/main/game
  ✗ Unity project missing
    Unity project directory not found: /Users/.../variants/main/unity

Abort: Fix issues before running export

Hint: Run 'erenshor download' first
```

**Scenario 2: User runs deploy without export**
```bash
$ erenshor wiki update

Precondition checks:
  ✗ Database not found
    SQLite database missing: /Users/.../variants/main/erenshor-main.sqlite

Abort: Fix issues before deploying

Hint: Run 'erenshor export' first
```

**Scenario 3: All preconditions pass**
```bash
$ erenshor export

Precondition checks:
  ✓ Unity project exists
  ✓ Editor scripts linked
  ✓ Unity executable found

All precondition checks passed

Starting Unity export...
[... export proceeds normally ...]
```

---

## Issue 2: Uncompressed Backups for Diffs

### Requirements

From feedback:
> "Is it really useful to zip the backups? We want them primarily to run different types of diffs (e.g., compare DB data to older game versions, compare source code of scripts to identify new functionality, etc.). Is this still easy to do if the files are zipped up? We do NOT need any restoration from backups. After all, the game will never revert, and if it does, we can just recreate everything from the 'new' / 'old' version anyway. So backups really are just a feature for identifying changes across versions."

**Key Points**:
1. Primary use: Running diffs (DB data, source code)
2. No restoration needed (can recreate from game version)
3. Zipping makes diffs harder
4. Want to identify changes across game versions

### Updated Backup Structure

**New Layout** (uncompressed):
```
.erenshor/backups/
├── main/
│   ├── build-20370413/
│   │   ├── metadata.json              # Backup metadata
│   │   ├── database.sqlite            # Raw SQLite (no compression)
│   │   ├── game-scripts/              # Raw C# files (no tar.gz)
│   │   │   ├── CharacterController.cs
│   │   │   ├── ItemManager.cs
│   │   │   ├── QuestSystem.cs
│   │   │   └── ... (842 files)
│   │   └── config.toml                # Config snapshot
│   ├── build-20456789/
│   │   └── ... (same structure)
│   └── latest -> build-20456789/      # Symlink to latest
├── playtest/
│   └── build-12345678/
│       └── ...
└── demo/
    └── build-98765432/
        └── ...
```

**Benefits**:
- ✅ Easy to browse files
- ✅ Easy to diff databases: `diff database1.sqlite database2.sqlite`
- ✅ Easy to diff scripts: `diff -r game-scripts1/ game-scripts2/`
- ✅ Can open SQLite with any viewer
- ✅ Can grep through source code
- ✅ No extraction step needed

**Drawbacks**:
- ❌ Larger disk usage (no compression)
- ❌ More inodes used (many files)

**Mitigation**:
- Show disk usage when creating backups
- Let user decide when to clean up old backups
- Disk space is cheap, convenience is valuable

### Diff Workflows

**Diff Databases Between Builds**:
```bash
# Using sqlite3
sqlite3 .erenshor/backups/main/build-20370413/database.sqlite

# Using SQLite browser
sqlitebrowser .erenshor/backups/main/build-20370413/database.sqlite

# Compare item counts
$ sqlite3 .erenshor/backups/main/build-20370413/database.sqlite "SELECT COUNT(*) FROM Item"
156

$ sqlite3 .erenshor/backups/main/build-20456789/database.sqlite "SELECT COUNT(*) FROM Item"
163

# New items added: 163 - 156 = 7

# Find new items
sqlite3 .erenshor/backups/main/build-20456789/database.sqlite \
  "SELECT ItemName FROM Item WHERE Id NOT IN (
    SELECT Id FROM (SELECT * FROM Item)
  )"

# Or use schema diff tools
sqldiff \
  .erenshor/backups/main/build-20370413/database.sqlite \
  .erenshor/backups/main/build-20456789/database.sqlite
```

**Diff Game Scripts Between Builds**:
```bash
# Compare directories
diff -r \
  .erenshor/backups/main/build-20370413/game-scripts/ \
  .erenshor/backups/main/build-20456789/game-scripts/

# Find new files
comm -13 \
  <(ls .erenshor/backups/main/build-20370413/game-scripts/ | sort) \
  <(ls .erenshor/backups/main/build-20456789/game-scripts/ | sort)

# Compare specific file
diff \
  .erenshor/backups/main/build-20370413/game-scripts/QuestSystem.cs \
  .erenshor/backups/main/build-20456789/game-scripts/QuestSystem.cs

# Grep for new functionality
grep -r "NewFeature" .erenshor/backups/main/build-20456789/game-scripts/
```

**Diff Configs Between Builds**:
```bash
diff \
  .erenshor/backups/main/build-20370413/config.toml \
  .erenshor/backups/main/build-20456789/config.toml
```

### Space Considerations

**Estimate Backup Sizes**:
- Database: ~12-15 MB per variant
- Game scripts: ~5-10 MB per variant (842 files)
- Config: <1 KB
- **Total per backup**: ~20 MB

**Example with 10 game builds**:
- 10 backups × 20 MB = 200 MB per variant
- 3 variants × 200 MB = 600 MB total

**Conclusion**: Disk usage is negligible for modern systems.

**Show Space on Create**:
```bash
$ erenshor export

[... export proceeds ...]

Creating backup for build 20456789...
  Database: 14.2 MB
  Game scripts: 8.5 MB (842 files)
  Config: 0.5 KB
  Total backup size: 22.7 MB

Backup created: .erenshor/backups/main/build-20456789/

Total backups for main: 3
Total disk usage: 68.1 MB
```

### Implementation Changes

**Update BackupService**:
```python
class BackupService:
    def _backup_database(self, source: Path, dest: Path) -> int:
        """Copy database without compression.

        Returns:
            Size in bytes
        """
        shutil.copy2(source, dest)
        return dest.stat().st_size

    def _backup_scripts(self, source_dir: Path, dest_dir: Path) -> tuple[int, int]:
        """Copy game scripts directory without compression.

        Returns:
            (total_size_bytes, file_count)
        """
        shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)

        # Calculate size and count
        total_size = 0
        file_count = 0
        for file in dest_dir.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
                file_count += 1

        return total_size, file_count

    def create_backup(
        self,
        variant: str,
        database_path: Path,
        game_scripts_dir: Path,
        config_path: Path
    ) -> Path | None:
        """Create or update backup for current game build."""
        # ... precondition checks ...

        # Copy files (no compression)
        db_size = self._backup_database(database_path, temp_dir / "database.sqlite")
        scripts_size, scripts_count = self._backup_scripts(
            game_scripts_dir,
            temp_dir / "game-scripts"
        )
        config_size = (temp_dir / "config.toml").stat().st_size

        total_size = db_size + scripts_size + config_size

        # Show size to user
        logger.info(f"  Database: {format_bytes(db_size)}")
        logger.info(f"  Game scripts: {format_bytes(scripts_size)} ({scripts_count} files)")
        logger.info(f"  Config: {format_bytes(config_size)}")
        logger.info(f"  Total backup size: {format_bytes(total_size)}")

        # ... rest of backup logic ...

        # Show total disk usage
        all_backups = self.list_backups(variant)
        total_disk = sum(b["total_size"] for b in all_backups)
        logger.info(f"\nTotal backups for {variant}: {len(all_backups)}")
        logger.info(f"Total disk usage: {format_bytes(total_disk)}")

        return backup_dir
```

---

## Issue 3: Simplified Template Architecture

### Survey of ACTUAL Template Usage

From old implementation analysis:

**Templates Currently Used** (from `items.py` transformer):
1. **{{Item}}** - Base infobox for all items (source fields for weapons/armor, full infobox for others)
2. **{{Fancy-weapon}}** - Weapon stat table (3 per page: Normal, Blessed, Godly)
3. **{{Fancy-armor}}** - Armor stat table (3 per page: Normal, Blessed, Godly)
4. **{{Fancy-charm}}** - Charm display template (1 per page)

**Legacy Templates (TO BE REMOVED)**:
1. ~~{{Weapon}}~~ - Replaced by {{Item}} + {{Fancy-weapon}} table
2. ~~{{Armor}}~~ - Replaced by {{Item}} + {{Fancy-armor}} table
3. ~~{{Consumable}}~~ - Replaced by {{Item}}
4. ~~{{Mold}}~~ - Replaced by {{Item}}
5. ~~{{Ability Books}} / {{Ability_Books}}~~ - Replaced by {{Item}}
6. ~~{{Auras}}~~ - Replaced by {{Item}}

**Evidence from `items.py` (line 159)**:
```python
pattern = re.compile(
    r"^\{\{\s*(Weapon|Armor|Auras|Ability Books|Ability_Books|Consumable|Mold|Item)"
)
return pattern.sub("{{" + target_name, body, count=1)
```

**Target names (line 146-154)**:
- Weapons/Armor/Charm/Aura/General/Consumable → `"Item"`
- Ability books → `"Ability Books"` (NOTE: User says to use {{Item}} instead)
- Molds → `"Mold"` (NOTE: User says to use {{Item}} instead)

**User Clarification**:
> "I don't think we're still using all the (item) templates that you mentioned. At the very least, we decided to discontinue Consumable templates and use the basic Item templates for those instead. Not sure about molds and ability books."

> "Also, Weapon and Armor ONLY use the Fancy-Weapon and Fancy-Armor templates - the non-stat-related info (drop location, vendors, ...) use the basic {{Item ...}} template."

> "Also, please beware that, e.g., Weapon and Armor pages use multiple templates on the same page (one {{Item ...}} and three {{Fancy-Weapon ...}} / {{Fancy-Armor ...}} each)."

### Legacy Templates (To Remove)

**Templates to Remove from Old Pages**:
1. `{{Consumable ...}}` → Replace with `{{Item ...}}`
2. `{{Weapon ...}}` → Replace with `{{Item ...}}` (but keep `{{Fancy-weapon}}` tables)
3. `{{Armor ...}}` → Replace with `{{Item ...}}` (but keep `{{Fancy-armor}}` tables)
4. `{{Mold ...}}` → Replace with `{{Item ...}}`
5. `{{Ability Books ...}}` / `{{Ability_Books ...}}` → Replace with `{{Item ...}}`
6. `{{Auras ...}}` → Replace with `{{Item ...}}`

**Removal Logic**:
```python
# When updating page, detect and replace legacy templates

class ContentMerger:
    def merge(self, original: str, generated: str, ...) -> str:
        """Merge generated content with original page."""

        # Step 1: Remove legacy templates
        cleaned = self._remove_legacy_templates(original)

        # Step 2: Merge with generated content
        merged = self._merge_infobox(cleaned, generated)

        return merged

    def _remove_legacy_templates(self, page_text: str) -> str:
        """Remove discontinued templates and replace with {{Item}}."""
        code = mw_parse(page_text)

        legacy_names = [
            "Weapon", "Armor", "Consumable", "Mold",
            "Ability Books", "Ability_Books", "Auras"
        ]

        for template in code.filter_templates():
            name = template.name.strip()
            if name in legacy_names:
                # Extract params from legacy template
                params = self._extract_params(template)

                # Build {{Item}} template with same params
                item_template = self._build_item_template(params)

                # Replace legacy with {{Item}}
                code.replace(template, item_template)

        return str(code)
```

### Current Templates (To Use)

**1. {{Item}}** - Universal infobox
- **Used for**: All item types
- **Content**:
  - Source fields (vendors, drops, quests, crafting)
  - Basic stats (for non-weapon/armor items)
  - Description, lore
- **Example**:
```wikitext
{{Item
|name=Iron Sword
|image=Iron Sword.png
|imagecaption=
|type=
|vendorsource=[[Blacksmith Vendor]]
|source=[[Goblin Warrior]]
|othersource=[[Mining]]
|questsource=[[Quest: Forging Basics]]
|relatedquest=
|craftsource=[[Crafting]]
|componentfor=
|relic=
|classes=Warrior, Duelist
|effects=
|damage=
|delay=
|dps=
|description=A sturdy iron blade
|buy=100
|sell=25
|itemid=1234
}}
```

**2. {{Fancy-weapon}}** - Weapon stats (3 tiers)
- **Used for**: Weapon pages ONLY
- **Content**: Weapon stats for one tier (Normal/Blessed/Godly)
- **Quantity**: 3 per weapon page
- **Placement**: After {{Item}} infobox, inside table
- **Example**:
```wikitext
{{Item|...}}

{| class="wikitable" style="text-align:center; width:100%"
! Normal !! Blessed !! Godly
|-
| {{Fancy-weapon
  |image=Iron Sword.png|60px
  |name=Iron Sword
  |type=One-Handed Melee
  |str=10|end=5|dex=0|agi=0|int=0|wis=0|cha=0|res=0
  |damage=50|delay=2.0
  |health=0|mana=0
  |armor=0|magic=0|poison=0|elemental=0|void=0
  |description=A sturdy iron blade
  |arcanist=|duelist=True|druid=|paladin=|stormcaller=
  |relic=
  |proc_name=|proc_desc=|proc_chance=|proc_style=
  |tier=Normal
  }}
| {{Fancy-weapon|...|tier=Blessed}}
| {{Fancy-weapon|...|tier=Godly}}
|}
```

**3. {{Fancy-armor}}** - Armor stats (3 tiers)
- **Used for**: Armor pages ONLY
- **Content**: Armor stats for one tier (Normal/Blessed/Godly)
- **Quantity**: 3 per armor page
- **Placement**: After {{Item}} infobox, inside table
- **Example**:
```wikitext
{{Item|...}}

{| class="wikitable" style="text-align:center; width:100%"
! Normal !! Blessed !! Godly
|-
| {{Fancy-armor
  |image=Iron Helmet.png|60px
  |name=Iron Helmet
  |type=|slot=Head
  |str=5|end=10|dex=0|agi=0|int=0|wis=0|cha=0|res=0
  |health=50|mana=0
  |armor=20|magic=5|poison=0|elemental=0|void=0
  |description=A protective iron helmet
  |arcanist=|duelist=True|druid=|paladin=|stormcaller=
  |relic=
  |proc_name=|proc_desc=|proc_chance=|proc_style=
  |tier=Normal
  }}
| {{Fancy-armor|...|tier=Blessed}}
| {{Fancy-armor|...|tier=Godly}}
|}
```

**4. {{Fancy-charm}}** - Charm display
- **Used for**: Charm pages ONLY
- **Content**: Charm stats and effects
- **Quantity**: 1 per charm page
- **Placement**: After {{Item}} infobox
- **Example**:
```wikitext
{{Item|...}}

{{Fancy-charm
|image=Charm of Protection.png
|name=Charm of Protection
|stats=+10 Armor, +5% Defense
|effect=Grants damage reduction
|...
}}
```

### Template Removal Logic

**Detect and Replace**:
```python
class LegacyTemplateRemover:
    """Remove discontinued templates and replace with current templates."""

    LEGACY_TO_CURRENT = {
        "Weapon": "Item",
        "Armor": "Item",
        "Consumable": "Item",
        "Mold": "Item",
        "Ability Books": "Item",
        "Ability_Books": "Item",
        "Auras": "Item",
    }

    def remove_legacy_templates(self, page_text: str) -> str:
        """Replace legacy templates with {{Item}}.

        Args:
            page_text: Original wiki page text

        Returns:
            Updated page text with legacy templates replaced
        """
        code = mw_parse(page_text)

        for template in list(code.filter_templates()):
            name = template.name.strip()

            if name in self.LEGACY_TO_CURRENT:
                # Get replacement template name
                new_name = self.LEGACY_TO_CURRENT[name]

                # Change template name
                template.name = new_name

                logger.info(f"Replaced {{{{'{name}'}}} with {{{{'{new_name}'}}}}")

        return str(code)
```

### Composition-Based Architecture

**Problem**: Avoid template inheritance complexity.

**Solution**: Use reusable components that can be included in multiple templates.

**Shared Components**:
1. **Source Fields** - Used by all item types
2. **Stat Fields** - Used by weapons, armor, charms
3. **Effect Fields** - Used by consumables, ability books
4. **Crafting Fields** - Used by craftable items, molds

**Template Structure**:
```
templates/wiki/items/
├── item.j2                    # {{Item}} template
├── fancy_weapon_template.j2   # {{Fancy-weapon}} template (single tier)
├── fancy_weapon_table.j2      # Fancy weapon table wrapper
├── fancy_armor_template.j2    # {{Fancy-armor}} template (single tier)
├── fancy_armor_table.j2       # Fancy armor table wrapper
├── fancy_charm.j2             # {{Fancy-charm}} template
└── shared/
    ├── sources.j2             # Source fields (reusable component)
    ├── stats.j2               # Stat fields (reusable component)
    ├── effects.j2             # Effect fields (reusable component)
    └── crafting.j2            # Crafting fields (reusable component)
```

**Example: item.j2 Using Shared Components**:
```jinja2
{# templates/wiki/items/item.j2 #}
{{Item
|name={{ name }}
|image={{ image }}
|imagecaption={{ imagecaption }}
|type={{ type }}

{# Include shared source component #}
{% include 'shared/sources.j2' %}

{# Include shared stat component (if not weapon/armor) #}
{% if not is_weapon and not is_armor %}
{% include 'shared/stats.j2' %}
{% endif %}

{# Include shared effect component (if applicable) #}
{% if has_effects %}
{% include 'shared/effects.j2' %}
{% endif %}

{# Include shared crafting component (if applicable) #}
{% if has_crafting %}
{% include 'shared/crafting.j2' %}
{% endif %}

|description={{ description }}
|buy={{ buy }}
|sell={{ sell }}
|itemid={{ itemid }}
}}
```

**Example: shared/sources.j2**:
```jinja2
{# templates/wiki/items/shared/sources.j2 #}
{% if vendorsource %}
|vendorsource={{ vendorsource }}
{% endif %}
{% if source %}
|source={{ source }}
{% endif %}
{% if othersource %}
|othersource={{ othersource }}
{% endif %}
{% if questsource %}
|questsource={{ questsource }}
{% endif %}
{% if relatedquest %}
|relatedquest={{ relatedquest }}
{% endif %}
{% if craftsource %}
|craftsource={{ craftsource }}
{% endif %}
{% if componentfor %}
|componentfor={{ componentfor }}
{% endif %}
```

**Benefits**:
- ✅ DRY - source fields defined once
- ✅ Consistent - all templates use same source formatting
- ✅ Easy to update - change in one place
- ✅ No inheritance complexity

### Implementation Plan

**Phase 1: Create Base Templates**
1. Create `item.j2` with shared components
2. Create `fancy_weapon_template.j2`
3. Create `fancy_armor_template.j2`
4. Create `fancy_charm.j2`

**Phase 2: Create Shared Components**
5. Create `shared/sources.j2`
6. Create `shared/stats.j2`
7. Create `shared/effects.j2`
8. Create `shared/crafting.j2`

**Phase 3: Generators**
9. Create item generators (one per type)
10. Each generator prepares data for template rendering
11. Test with fixture data

**Phase 4: Legacy Removal**
12. Implement `LegacyTemplateRemover`
13. Integrate with content merger
14. Test with real wiki pages

---

## Issue 4: Configuration-Driven Field Preservation

### Requirements

From feedback:
> "I don't think 'vandalism detection' is something we can reliably do. This is just feature creep that would blow up our implementation WAY too much. I think we MUST use manual configuration here that defines which fields should be preserved."

> "Probably best to just keep the old value then until we have our update logic well enough implemented that we can confidently replace those values (i.e., no merging, only replacements when we are confident about them)."

> "Or perhaps some way to define custom resolution strategies that can be set for individual template fields. Kinda like that idea actually. Can you design a (simple) system for that?"

> "I don't think reacting to recentchanges will get us any useful solution. Too much effort, too many things that can go wrong. And we want full automation, which is not really feasible with a system that is so brittle."

> "If we can get notified of manual edits anywhere on the page, that would still be great though -> allows us to list pages that might need manual intervention / validation after the update has finished (ideally: locally, so we can handle things before they go live)."

**Key Points**:
1. NO automatic vandalism detection
2. MUST use manual configuration for field preservation
3. No complex merging - keep old OR replace (confidently)
4. Custom resolution strategies per field (user likes this idea)
5. NO automatic preservation via recentchanges detection
6. Still useful: Notify of manual edits → list pages needing review
7. Want full automation, not brittle systems
8. Local review before pushing to wiki

### Simple Configuration Format

**Configuration File**: `config.toml` or `.erenshor/field-preservation.toml`

```toml
# Field preservation configuration
# Defines which fields to preserve when updating wiki pages

[preservation]
# Global policy: "preserve", "override", or "custom"
default_policy = "override"

# Field-specific policies
[preservation.fields]

# Always preserve these fields (user-curated content)
imagecaption = "preserve"
notes = "preserve"
trivia = "preserve"

# Custom resolution for source fields
othersource = "merge_sources"
relatedquest = "preserve_if_not_empty"

# Always override with generated data
damage = "override"
armor = "override"
level = "override"
stats = "override"

# Conditional preservation
type = "preserve_for_general_items"  # Only preserve for non-weapon/armor items

# Custom handlers
[preservation.custom_handlers]
# Python callables for complex resolution logic

merge_sources = "erenshor.application.services.resolution:merge_source_fields"
preserve_if_not_empty = "erenshor.application.services.resolution:preserve_if_not_empty"
preserve_for_general_items = "erenshor.application.services.resolution:preserve_for_general_items"
```

**Simple Policies**:
- `"preserve"` - Always keep old value
- `"override"` - Always use new value
- `"merge_sources"` - Merge old + new (for source fields)
- `"preserve_if_not_empty"` - Keep old if it has content
- `"custom:<handler_name>"` - Use custom resolution function

### Custom Resolution Strategy System

**Architecture**:
```python
# src/erenshor/application/services/field_resolution.py

from typing import Protocol

class ResolutionStrategy(Protocol):
    """Protocol for field resolution strategies."""

    def resolve(
        self,
        field_name: str,
        old_value: str,
        new_value: str,
        context: dict
    ) -> str:
        """Resolve conflict between old and new values.

        Args:
            field_name: Template field name
            old_value: Value from original wiki page
            new_value: Value from generated content
            context: Additional context (item type, etc.)

        Returns:
            Resolved value to use
        """
        ...

class PreserveStrategy:
    """Always preserve old value."""

    def resolve(self, field_name: str, old_value: str, new_value: str, context: dict) -> str:
        return old_value

class OverrideStrategy:
    """Always use new value."""

    def resolve(self, field_name: str, old_value: str, new_value: str, context: dict) -> str:
        return new_value

class MergeSourcesStrategy:
    """Merge source fields (deduplicate)."""

    def resolve(self, field_name: str, old_value: str, new_value: str, context: dict) -> str:
        from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR

        # Split into parts
        old_parts = [p.strip() for p in old_value.split(WIKITEXT_LINE_SEPARATOR) if p.strip()]
        new_parts = [p.strip() for p in new_value.split(WIKITEXT_LINE_SEPARATOR) if p.strip()]

        # Deduplicate (preserve order from new, append unique old)
        merged = new_parts.copy()
        for part in old_parts:
            if part not in merged:
                merged.append(part)

        return WIKITEXT_LINE_SEPARATOR.join(merged)

class PreserveIfNotEmptyStrategy:
    """Preserve old value if it's not empty."""

    def resolve(self, field_name: str, old_value: str, new_value: str, context: dict) -> str:
        if old_value.strip():
            return old_value
        return new_value

class PreserveForGeneralItemsStrategy:
    """Preserve for general items, override for weapon/armor."""

    def resolve(self, field_name: str, old_value: str, new_value: str, context: dict) -> str:
        item_kind = context.get("item_kind", "general")

        if item_kind in ("weapon", "armor"):
            # Override for weapon/armor (handled by Fancy tables)
            return new_value
        else:
            # Preserve for other items
            return old_value if old_value.strip() else new_value

# Registry of strategies
BUILTIN_STRATEGIES = {
    "preserve": PreserveStrategy(),
    "override": OverrideStrategy(),
    "merge_sources": MergeSourcesStrategy(),
    "preserve_if_not_empty": PreserveIfNotEmptyStrategy(),
    "preserve_for_general_items": PreserveForGeneralItemsStrategy(),
}

class FieldResolver:
    """Resolve field conflicts using configured strategies."""

    def __init__(self, config: dict):
        """Initialize field resolver.

        Args:
            config: Configuration dict from config.toml
        """
        self.config = config
        self.default_policy = config.get("preservation", {}).get("default_policy", "override")
        self.field_policies = config.get("preservation", {}).get("fields", {})
        self.strategies = BUILTIN_STRATEGIES.copy()

        # Load custom handlers
        custom_handlers = config.get("preservation", {}).get("custom_handlers", {})
        for name, handler_path in custom_handlers.items():
            if name not in self.strategies:
                # Dynamically load custom handler
                self.strategies[name] = self._load_handler(handler_path)

    def resolve(
        self,
        field_name: str,
        old_value: str,
        new_value: str,
        context: dict
    ) -> str:
        """Resolve field using configured strategy.

        Args:
            field_name: Template field name
            old_value: Value from original wiki page
            new_value: Value from generated content
            context: Additional context (item type, etc.)

        Returns:
            Resolved value to use
        """
        # Get policy for this field
        policy = self.field_policies.get(field_name, self.default_policy)

        # Get strategy
        strategy = self.strategies.get(policy)

        if not strategy:
            logger.warning(f"Unknown resolution strategy: {policy}, using default")
            strategy = self.strategies[self.default_policy]

        # Resolve
        return strategy.resolve(field_name, old_value, new_value, context)

    def _load_handler(self, handler_path: str):
        """Dynamically load custom handler from path.

        Args:
            handler_path: Module path like "package.module:function"

        Returns:
            Loaded handler callable
        """
        module_path, handler_name = handler_path.split(":")
        module = __import__(module_path, fromlist=[handler_name])
        return getattr(module, handler_name)
```

### Manual Edit Notification System

**Purpose**: Detect manual edits (but don't auto-preserve) and notify user for review.

**Design**:
1. After generating pages locally
2. Query MediaWiki `recentchanges` for each page
3. Detect edits by non-bot users since last update
4. Store list of pages with manual edits
5. Show notification to user
6. User reviews locally before pushing

**Implementation**:
```python
# src/erenshor/application/services/manual_edit_detector.py

from datetime import datetime

class ManualEditDetector:
    """Detect manual edits to wiki pages (notification only, no auto-preservation)."""

    def __init__(self, wiki_client: MediaWikiClient):
        self.wiki_client = wiki_client
        self.bot_users = ["DataMinerBot"]  # Configure bot usernames

    def detect_manual_edits(
        self,
        page_titles: list[str],
        since: datetime
    ) -> list[ManualEditNotification]:
        """Detect which pages have manual edits since timestamp.

        Args:
            page_titles: List of wiki page titles to check
            since: Only check edits since this timestamp

        Returns:
            List of pages with manual edits (for notification)
        """
        notifications = []

        for page_title in page_titles:
            # Query recentchanges for this page
            changes = self.wiki_client.get_recent_changes(
                page_title=page_title,
                start=since,
                end=datetime.now()
            )

            # Filter for manual edits (non-bot users)
            manual_changes = [
                c for c in changes
                if c.user not in self.bot_users
            ]

            if manual_changes:
                # Page has manual edits - notify
                notifications.append(ManualEditNotification(
                    page_title=page_title,
                    edit_count=len(manual_changes),
                    last_editor=manual_changes[-1].user,
                    last_edit_time=manual_changes[-1].timestamp,
                    last_edit_comment=manual_changes[-1].comment
                ))

        return notifications

@dataclass
class ManualEditNotification:
    """Notification about manual edits to a page."""
    page_title: str
    edit_count: int
    last_editor: str
    last_edit_time: datetime
    last_edit_comment: str
```

**Usage in Wiki Update Workflow**:
```python
# In wiki update command

def wiki_update_command(variant: str):
    """Update wiki pages."""

    # Step 1: Generate pages locally
    logger.info("Generating wiki pages...")
    generated_pages = generate_all_pages(variant)

    # Step 2: Fetch existing pages from wiki
    logger.info("Fetching existing pages from wiki...")
    existing_pages = fetch_wiki_pages([p.title for p in generated_pages])

    # Step 3: Merge generated with existing
    logger.info("Merging generated content with existing pages...")
    merged_pages = merge_all_pages(generated_pages, existing_pages)

    # Step 4: Detect manual edits (for notification only)
    logger.info("Checking for manual edits...")
    last_update = get_last_update_time(variant)
    detector = ManualEditDetector(wiki_client)
    manual_edits = detector.detect_manual_edits(
        page_titles=[p.title for p in generated_pages],
        since=last_update
    )

    # Step 5: Show notifications
    if manual_edits:
        logger.warning(f"\n⚠ {len(manual_edits)} pages have manual edits since last update:")
        for edit in manual_edits:
            logger.warning(f"  - {edit.page_title}")
            logger.warning(f"    Last edited by {edit.last_editor} on {edit.last_edit_time}")
            logger.warning(f"    Comment: {edit.last_edit_comment}")

        # Save list for local review
        save_manual_edit_list(manual_edits, variant)

        logger.warning("\nReview these pages before pushing:")
        logger.warning(f"  File: .erenshor/wiki/manual-edits-{variant}.json")
        logger.warning("  Command: erenshor wiki review-manual-edits")

    # Step 6: Save merged pages locally (for review)
    logger.info("\nSaving merged pages locally...")
    save_merged_pages(merged_pages, variant)

    logger.info(f"\nMerged pages saved to: .erenshor/wiki/merged/{variant}/")
    logger.info("Review pages before pushing to wiki")
    logger.info("\nNext steps:")
    logger.info("  1. Review manual edits (if any)")
    logger.info("  2. Review merged pages")
    logger.info("  3. Push to wiki: erenshor wiki push")
```

### Local Review Workflow

**Files Created**:
```
.erenshor/wiki/
├── merged/
│   └── main/
│       ├── Iron_Sword.txt      # Merged wiki page (ready to push)
│       ├── Health_Potion.txt
│       └── ... (all pages)
├── manual-edits-main.json      # List of pages with manual edits
└── last-update-main.json       # Timestamp of last update
```

**Review Commands**:
```bash
# List pages with manual edits
$ erenshor wiki review-manual-edits

Pages with manual edits (3):

1. Iron Sword
   Last edited by: WikiUser123 on 2025-10-15 14:30:00
   Comment: "Added missing location info"

2. Health Potion
   Last edited by: Editor456 on 2025-10-16 10:15:00
   Comment: "Fixed typo in description"

3. Magic Amulet
   Last edited by: Contributor789 on 2025-10-14 09:00:00
   Comment: ""

# View merged content for specific page
$ erenshor wiki view-merged "Iron Sword"

[Shows merged wiki page content]

# Compare with current wiki version
$ erenshor wiki diff "Iron Sword"

[Shows diff between merged and current wiki]

# Push to wiki (after review)
$ erenshor wiki push

Pushing 247 pages to wiki...
  Pages with manual edits will be listed again for confirmation

Confirm push? [y/N]: y

Pushed 247 pages successfully
```

### Implementation Approach

**Task Breakdown**:
1. Create `FieldResolver` class with builtin strategies
2. Create configuration schema in `config.toml`
3. Create `ManualEditDetector` class
4. Integrate with content merger
5. Add review commands to CLI
6. Create local review workflow

**Code Structure**:
```python
# src/erenshor/application/services/content_merger.py

class ContentMerger:
    """Merge generated content with existing wiki pages."""

    def __init__(
        self,
        field_resolver: FieldResolver,
        manual_edit_detector: ManualEditDetector
    ):
        self.field_resolver = field_resolver
        self.manual_edit_detector = manual_edit_detector

    def merge(
        self,
        original: str,
        generated: str,
        page_title: str,
        item_kind: str
    ) -> str:
        """Merge generated content with original page.

        Args:
            original: Original wiki page content
            generated: Generated page content
            page_title: Page title
            item_kind: Item kind (weapon, armor, general, etc.)

        Returns:
            Merged page content
        """
        # Parse templates
        orig_tpl = self._extract_infobox(original)
        gen_tpl = self._extract_infobox(generated)

        if not orig_tpl or not gen_tpl:
            # No infobox to merge, use generated
            return generated

        # Merge fields using resolver
        merged_tpl = gen_tpl.copy()

        for field_name in orig_tpl.keys():
            old_value = orig_tpl.get(field_name, "").strip()
            new_value = gen_tpl.get(field_name, "").strip()

            if old_value == new_value:
                # No conflict
                continue

            # Resolve using configured strategy
            context = {
                "page_title": page_title,
                "item_kind": item_kind,
            }

            resolved = self.field_resolver.resolve(
                field_name, old_value, new_value, context
            )

            merged_tpl[field_name] = resolved

        # Render merged template
        merged_content = self._render_template(merged_tpl)

        return merged_content
```

---

## Issue 5: Concurrent Edit Strategy

### Decision

From feedback:
> "Eh, how would you detect this? We can't do checks on upload, because fetching individual page contents for each pushed page consumes too many API requests (-> rate limiting). And in the final implementation, the fetch -> update -> push process shouldn't take very long anyway. So I guess we just overwrite whatever is there?"

**Strategy**: Just overwrite whatever is on wiki during push.

### Rationale

**Why this is acceptable**:
1. Fetch → Update → Push is fast (minutes, not hours)
2. Unlikely someone edits during this short window
3. Checking on upload would require fetching each page again (rate limiting)
4. If it happens, we can always revert on wiki
5. Manual edit detector will catch it next time

**Risk Mitigation**:
- Show clear timestamps in logs
- Document when update started/finished
- If user sees concurrent edit, they can revert and re-run

**No Special Handling Required**.

---

## Updated Recommendations

### Removed Features

1. ❌ Zipped backups
2. ❌ Automatic vandalism detection
3. ❌ Complex merge strategies
4. ❌ Auto-preservation via recentchanges
5. ❌ Concurrent edit detection on upload
6. ❌ Legacy template support (Consumable, Weapon, Armor, Mold, Ability Books, Auras)

### Simplified Features

1. ✅ Backups: Uncompressed directories (easy diffs)
2. ✅ Field preservation: Manual configuration only
3. ✅ Resolution: Keep old OR replace (no complex merging)
4. ✅ Templates: Composition over inheritance
5. ✅ Conflict handling: Just overwrite on push

### New Features

1. ✅ Precondition checks before all commands
2. ✅ Atomic backup operations (temp dir + rename)
3. ✅ Custom resolution strategies per field
4. ✅ Manual edit notifications (detect but don't auto-preserve)
5. ✅ Local review workflow before pushing
6. ✅ Legacy template removal logic

### Implementation Priority

**Phase 1: Foundation**
1. Precondition system (fail fast)
2. Uncompressed backup service
3. Field resolver with builtin strategies
4. Legacy template removal

**Phase 2: Templates**
5. Simplified template architecture
6. Shared components (composition)
7. Item generators (one per type)

**Phase 3: Review Workflow**
8. Manual edit detector
9. Local review commands
10. Push workflow with notifications

**Phase 4: Testing**
11. Test precondition checks
12. Test field resolution strategies
13. Test template composition
14. Integration tests

---

## Updated Phase 3 Task Changes

### Tasks to Remove

**From Original Plan**:
- ❌ Task 1.2: "Detect database changes via SHA256 hash"
- ❌ Task 2.3a: "Automatic vandalism detection"
- ❌ Task 2.3b: "Complex merge strategies"
- ❌ Task 2.5a: "Interactive conflict resolution CLI"
- ❌ Milestone 5: Documentation tasks (defer to backlog)

### Tasks to Modify

**Task 1.2 - Backup Service** (REWRITE):
- ❌ Old: "Automatic backups on database version changes"
- ✅ New: "Automatic backups on game build changes"
- ✅ New: "Uncompressed backup structure"
- ✅ New: "Show disk usage on create"
- ✅ New: "Atomic operations (temp dir + rename)"

**Task 1.X - Add Precondition Checks** (NEW):
- ✅ Create `PreconditionChecker` class
- ✅ Extract checks from doctor commands
- ✅ Add precondition calls to all commands
- ✅ Fail fast before destructive operations

**Task 2.2 - Page Generator** (SIMPLIFY):
- ❌ Old: "7+ specialized generators with inheritance"
- ✅ New: "Simple generators with composition"
- ✅ New: "Shared components for reusable parts"
- ✅ New: "Only 4 templates: Item, Fancy-weapon, Fancy-armor, Fancy-charm"

**Task 2.3 - Content Merger** (SIMPLIFY):
- ❌ Old: "Automatic detection via recentchanges"
- ✅ New: "Manual configuration for field preservation"
- ✅ New: "Custom resolution strategies per field"
- ✅ New: "No automatic preservation"

**Task 2.3a - Manual Edit Notifications** (NEW):
- ✅ Create `ManualEditDetector` class
- ✅ Query recentchanges (notification only)
- ✅ List pages needing review
- ✅ Local review workflow

**Task 2.3b - Legacy Template Removal** (NEW):
- ✅ Create `LegacyTemplateRemover` class
- ✅ Replace Consumable/Weapon/Armor/Mold/Ability Books/Auras with Item
- ✅ Test with real wiki pages

**Task 2.5 - Wiki Commands** (SIMPLIFY):
- ❌ Old: "Complex conflict resolution commands"
- ✅ New: "Simple review commands"
- ✅ New: "erenshor wiki review-manual-edits"
- ✅ New: "erenshor wiki view-merged <page>"
- ✅ New: "erenshor wiki diff <page>"
- ✅ New: "erenshor wiki push"

### Tasks to Add

**NEW Task 1.2a - Build ID Detection**:
- Implement `get_current_build_id()` in BackupService
- Test with all variants
- Handle missing manifest gracefully
- **Estimated**: 30 minutes

**NEW Task 1.2b - Precondition System**:
- Create `PreconditionChecker` class
- Implement core filesystem checks
- Extract checks from doctor commands
- Integrate with all commands
- **Estimated**: 2 hours

**NEW Task 2.2a - Template Composition**:
- Create shared components (sources, stats, effects, crafting)
- Create base templates using components
- Test composition approach
- **Estimated**: 1.5 hours

**NEW Task 2.3a - Field Resolution System**:
- Create `FieldResolver` class
- Implement builtin strategies
- Add configuration schema
- Test resolution logic
- **Estimated**: 2 hours

**NEW Task 2.3b - Manual Edit Notifications**:
- Create `ManualEditDetector` class
- Integrate MediaWiki recentchanges API
- Create notification workflow
- **Estimated**: 1.5 hours

**NEW Task 2.3c - Local Review Workflow**:
- Implement review commands
- Create local file structure
- Add diff functionality
- **Estimated**: 1 hour

**NEW Task 2.3d - Legacy Template Removal**:
- Create `LegacyTemplateRemover` class
- Add detection logic
- Add replacement logic
- Test with real pages
- **Estimated**: 1 hour

---

## Implementation Strategy

### Incremental Approach

**Week 1: Foundation**
1. Precondition system
2. Uncompressed backups
3. Field resolver (core)

**Week 2: Templates**
4. Shared components
5. Simplified generators
6. Legacy template removal

**Week 3: Review Workflow**
7. Manual edit detector
8. Review commands
9. Push workflow

**Week 4: Testing & Polish**
10. Unit tests
11. Integration tests
12. Documentation updates

### Testing Strategy

**Unit Tests**:
- Precondition checks (all scenarios)
- Field resolution strategies
- Template composition
- Legacy template removal

**Integration Tests**:
- Full backup workflow
- Full wiki update workflow
- Manual edit detection
- Local review workflow

**Manual Testing**:
- Test with real game data
- Test with real wiki pages
- Test manual edit scenarios
- Test concurrent operations

---

## Next Steps

1. **User Review**:
   - Review this v2 analysis
   - Confirm simplifications are acceptable
   - Approve removed/simplified features
   - Request any clarifications

2. **Update Phase 3 Plan**:
   - Remove tasks (vandalism detection, complex merging, etc.)
   - Simplify tasks (backups, templates, conflict resolution)
   - Add new tasks (preconditions, notifications, legacy removal)
   - Update estimates

3. **Begin Implementation**:
   - Start with precondition system (highest priority)
   - Move to uncompressed backups
   - Implement field resolver
   - Proceed with updated plan

---

**End of Analysis v2**
