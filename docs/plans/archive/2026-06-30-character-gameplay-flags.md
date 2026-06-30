---
title: Character Gameplay Flags
type: plan
status: implemented
created: 2026-06-30
archived: 2026-06-30
---

# Character Gameplay Flags

**Goal:** Export stable serialized character flags that affect gameplay and are not runtime caches or component references.

**Scope:** Exported fields are `CanNeverSeeInvis`, `DPSDummy`, `IsWyrm`, and `NoRun`. `NeverTrack` was excluded: it only controls `TrackEngagedTargets` UI target-frame visibility, not gameplay data worth exporting, so it remains ignored with a refined reason. `SeeInvisible`, `NoFlinch`, `OverrideAnimSpeed`, `ShrinkColliderOnDeath`, and `TargetRingMod` remain out of scope unless serialized-value inspection proves they should be treated as data fields.

## Tasks

### Task 1: Verify serialized-source status

- [x] Inspect playtest character prefab/scene values for the candidate fields.
- [x] Confirm each selected field is stable source data, not assigned only at runtime.
- [x] Record any rejected field as an ignored field-coverage entry with a code-backed reason.

### Task 2: Add selected raw export fields

- [x] Add selected fields to `src/Assets/Editor/Database/CharacterRecord.cs`.
- [x] Populate selected fields in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/CharacterListener.cs`.
- [x] Update `src/tools/ExportSurface/field-coverage.json` so selected fields are `captured` by `CharacterListener` and rejected fields have precise ignored reasons.

### Task 3: Add clean database fields

- [x] Add selected clean `characters` columns in `src/erenshor/application/processor/writer.py`.
- [x] Map selected raw fields in `src/erenshor/application/processor/characters.py`.
- [x] Keep booleans as integer booleans in SQLite, matching existing character flags.

### Task 4: Verify character output

- [x] Add or update focused processor/export tests that prove selected clean columns are populated from raw rows.
- [x] Run the focused tests.
- [x] Run `uv run erenshor -V playtest extract export`.
- [x] Run `uv run erenshor -V playtest extract code-facts`.
- [x] Run `uv run erenshor -V playtest extract build`.
- [x] Run affected tests and `uv run pytest` if schema or processor code changes.

## Acceptance

- Stable serialized gameplay flags are exported.
- Runtime-derived or presentation-only fields remain ignored with code-backed reasons.
- `field-coverage.json` reflects the reviewed baseline.
- Playtest export/build and focused tests pass.
