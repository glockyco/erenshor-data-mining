---
title: Ascension Stormcaller/Reaver Field Exports
type: plan
status: active
created: 2026-06-30
---

# Ascension Stormcaller/Reaver Field Exports

**Goal:** Export the Stormcaller and Reaver ascension effect fields that are present on `Ascension` assets but absent from the raw and clean databases.

**Scope:** This plan covers only scalar fields on `Ascension`: `ReloadHaste`, `LightningProcChance`, `NoCDPenaltyChance`, `KillshotChance`, and `TripleAttackChanceReav`.

## Tasks

### Task 1: Add raw export fields

- [ ] Add the five fields to `src/Assets/Editor/Database/AscensionRecord.cs`.
- [ ] Populate them in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/AscensionListener.cs` from the matching `Ascension` asset fields.
- [ ] Update `src/tools/ExportSurface/field-coverage.json` so the five fields are `captured` by `AscensionListener`.

### Task 2: Add clean database fields

- [ ] Add clean `ascensions` columns in `src/erenshor/application/processor/writer.py`.
- [ ] Map the raw fields in the ascension processing path.
- [ ] Preserve existing column names and naming style for ascension scalar fields.

### Task 3: Verify ascension output

- [ ] Add or update a focused processor/export test that proves the five clean columns are populated from raw rows.
- [ ] Run the focused test.
- [ ] Run `uv run erenshor -V playtest extract export`.
- [ ] Run `uv run erenshor -V playtest extract code-facts`.
- [ ] Run `uv run erenshor -V playtest extract build`.
- [ ] Run affected tests and `uv run pytest` if schema or processor code changes.

## Acceptance

- The raw `Ascensions` table contains the five Stormcaller/Reaver fields.
- The clean `ascensions` table contains corresponding columns.
- `field-coverage.json` has no ignored entries for these five fields.
- Playtest export/build and focused tests pass.
