# Backup Service Design Questions

**Date**: 2025-10-17
**Status**: Answered (ready for implementation)

## Questions and Answers

### Q1: Where are game C# scripts located?

**Answer**: Game C# scripts are located in the Unity project after AssetRipper extraction:
- **Path**: `variants/{variant}/unity/Assets/Scripts/Assembly-CSharp/*.cs`
- **Count**: ~385 C# files
- **Size**: Part of ~8.5MB total backup
- **Note**: These are NOT our editor scripts in `src/Assets/Editor/`

**Decision**: Backup the entire `Scripts` directory from Unity project.

### Q2: Which config files should be backed up?

**Answer**: Based on existing backup structure, NO config files are currently backed up. The old system only backs up:
1. Database file (`db/erenshor.sqlite`)
2. Game C# scripts (`src/*.cs`)

**Decision**: Match existing behavior - only backup database + game scripts. Config files (config.toml) are tracked in git and don't change per build.

### Q3: Should we backup the entire game scripts directory or filter specific files?

**Answer**: Backup entire Scripts directory (all game C# files).

**Rationale**:
- ~385 files, only ~8.5MB total
- Need all scripts for accurate diffing
- No performance concern with full backup
- Simpler implementation

**Decision**: Copy entire `Assets/Scripts/` directory recursively.

### Q4: What if build ID detection fails?

**Answer**: Build ID detection can fail if:
- Game not downloaded yet
- Manifest file missing
- Manifest file corrupted

**Decision**:
- Build ID is REQUIRED for backup creation
- Fail early with clear error message
- Use precondition check to ensure game is downloaded
- Let caller handle the error (don't create backup without build ID)

### Q5: Should we validate backup integrity after creation?

**Answer**: Yes, but minimal validation.

**Decision**:
- Check that database file was copied successfully (exists + size > 0)
- Check that scripts directory was copied successfully (exists + contains files)
- Write metadata.json with backup details
- No deep validation (checksums, file comparison) - atomic operations provide safety

### Q6: What's the backup directory location?

**Answer**: Based on config.toml line 64:
```toml
[variants.main]
backups = "$REPO_ROOT/variants/main/backups"
```

Each variant has its own backups directory.

**Decision**: Use config-based path `variants/{variant}/backups/`

### Q7: Backup naming convention?

**Answer**: Based on existing backups, current naming is:
- Format: `YYYYMMDD_HHMMSS_build{BUILD_ID}`
- Example: `20251014_085636_build20370413`

**Issue**: This creates multiple backups for same build ID!

**New Decision** (per Phase 3 plan):
- Format: `build-{BUILD_ID}`
- Example: `build-20370413`
- Re-running export on same build → overwrite old backup
- New build → create new backup
- Simpler naming, easier to understand

**Alternative considered**: `YYYY-MM-DD_build-{BUILD_ID}` (per plan diagram)

**Final Decision**: Use `build-{BUILD_ID}` only (cleaner, no date ambiguity).

### Q8: What metadata should be stored?

**Answer**: Create `metadata.json` with:
```json
{
  "variant": "main",
  "build_id": "20370413",
  "app_id": "2382520",
  "created_at": "2025-10-17T15:30:00Z",
  "database_path": "erenshor-main.sqlite",
  "database_size_bytes": 5812224,
  "scripts_count": 385,
  "scripts_size_bytes": 8912000,
  "total_size_bytes": 14724224
}
```

This provides:
- Build identification
- Creation timestamp
- Size metrics for UX
- File counts for validation

### Q9: Atomic operations - how to implement?

**Answer**: Use temp directory + rename pattern:
1. Create temp dir: `backups/.backup-{BUILD_ID}.tmp`
2. Copy all files to temp dir
3. Write metadata.json to temp dir
4. Rename temp dir to final name: `backups/build-{BUILD_ID}`

**Benefits**:
- If process fails/crashes, temp dir is left behind (no partial backup)
- Rename is atomic on most filesystems
- Easy to detect and clean up failed backups (*.tmp)

**Cleanup**: Remove any existing `build-{BUILD_ID}` directory before starting (overwrite behavior).

### Q10: How to calculate and display disk space?

**Answer**:
1. Use `Path.stat().st_size` for files
2. Recursively sum all file sizes
3. Format using human-readable units:
   - < 1024 bytes: "X bytes"
   - < 1024 KB: "X.X KB"
   - < 1024 MB: "X.X MB"
   - >= 1024 MB: "X.X GB"

4. Display in Rich panel:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃          Backup Created                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  Build ID: 20370413
  Database: 5.5 MB (1 file)
  Scripts:  8.5 MB (385 files)
  ────────────────────────────
  Total:    14.0 MB

  Location: variants/main/backups/build-20370413
```

## Implementation Summary

**What to backup**:
1. ✅ Database file: `variants/{variant}/erenshor-{variant}.sqlite`
2. ✅ Game C# scripts: `variants/{variant}/unity/Assets/Scripts/` (recursive)
3. ❌ Config files: Not needed (tracked in git, don't change per build)

**Backup structure**:
```
variants/{variant}/backups/
├── build-20370413/
│   ├── metadata.json         # Backup metadata
│   ├── database/
│   │   └── erenshor-main.sqlite
│   └── scripts/              # All game C# files
│       └── (385 .cs files)
```

**Key features**:
- ✅ Per build ID (not timestamp)
- ✅ Uncompressed (easy diffing)
- ✅ Atomic operations (temp dir + rename)
- ✅ Overwrite same build (re-export)
- ✅ Keep all builds (no cleanup)
- ✅ Show disk usage (human-readable)
- ✅ Rich-formatted output

**Preconditions**:
- Game must be downloaded (for build ID detection)
- Database must exist
- Unity project must exist (for game scripts)
- Sufficient disk space (check available vs backup size)

## Ready for Implementation

All questions answered. Proceeding with implementation.
