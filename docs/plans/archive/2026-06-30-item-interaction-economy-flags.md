---
title: Item Interaction and Economy Flags
type: plan
status: implemented
created: 2026-06-30
archived: 2026-06-30
---

# Item Interaction and Economy Flags

**Goal:** Export item flags that affect interaction, sale eligibility, and rarity behavior.

**Scope:** This plan covers only `Item.MustBeEquippedToClick`, `Item.PlayerCannotSell`, and `Item.RareItem`.

## Tasks

### Task 1: Add raw export fields

- [x] Add `MustBeEquippedToClick`, `PlayerCannotSell`, and `RareItem` to `src/Assets/Editor/Database/ItemRecord.cs`.
- [x] Populate them in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ItemListener.cs`.
- [x] Update `src/tools/ExportSurface/field-coverage.json` so the three fields are `captured` by `ItemListener`.

### Task 2: Add clean database fields

- [x] Add clean `items` columns in `src/erenshor/application/processor/writer.py`.
- [x] Map the raw fields in the item processing path.
- [x] Keep boolean values as integer booleans in SQLite, matching existing item flags.

### Task 3: Verify item output

- [x] Add or update a focused processor/export test that proves all three clean columns are populated from raw rows.
- [x] Run the focused test.
- [x] Run `uv run erenshor -V playtest extract export`.
- [x] Run `uv run erenshor -V playtest extract code-facts`.
- [x] Run `uv run erenshor -V playtest extract build`.
- [x] Run affected tests and `uv run pytest` if schema or processor code changes.

## Acceptance

- The raw `Items` table contains the three fields.
- The clean `items` table contains corresponding columns.
- `field-coverage.json` has no ignored entries for these three fields.
- Playtest export/build and focused tests pass.
