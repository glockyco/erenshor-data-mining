---
title: Item Interaction and Economy Flags
type: plan
status: active
created: 2026-06-30
---

# Item Interaction and Economy Flags

**Goal:** Export item flags that affect interaction, sale eligibility, and rarity behavior.

**Scope:** This plan covers only `Item.MustBeEquippedToClick`, `Item.PlayerCannotSell`, and `Item.RareItem`.

## Tasks

### Task 1: Add raw export fields

- [ ] Add `MustBeEquippedToClick`, `PlayerCannotSell`, and `RareItem` to `src/Assets/Editor/Database/ItemRecord.cs`.
- [ ] Populate them in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ItemListener.cs`.
- [ ] Update `src/tools/ExportSurface/field-coverage.json` so the three fields are `captured` by `ItemListener`.

### Task 2: Add clean database fields

- [ ] Add clean `items` columns in `src/erenshor/application/processor/writer.py`.
- [ ] Map the raw fields in the item processing path.
- [ ] Keep boolean values as integer booleans in SQLite, matching existing item flags.

### Task 3: Verify item output

- [ ] Add or update a focused processor/export test that proves all three clean columns are populated from raw rows.
- [ ] Run the focused test.
- [ ] Run `uv run erenshor -V playtest extract export`.
- [ ] Run `uv run erenshor -V playtest extract code-facts`.
- [ ] Run `uv run erenshor -V playtest extract build`.
- [ ] Run affected tests and `uv run pytest` if schema or processor code changes.

## Acceptance

- The raw `Items` table contains the three fields.
- The clean `items` table contains corresponding columns.
- `field-coverage.json` has no ignored entries for these three fields.
- Playtest export/build and focused tests pass.
