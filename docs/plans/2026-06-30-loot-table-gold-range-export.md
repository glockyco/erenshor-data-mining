---
title: LootTable Gold Range Export
type: plan
status: active
created: 2026-06-30
---

# LootTable Gold Range Export

**Goal:** Export static loot-table gold ranges separately from runtime loot roll state.

**Scope:** This plan covers `LootTable.MinGold` and `LootTable.MaxGold`. Runtime fields such as `MyGold`, `ActualDropsQual`, and `qualUps` remain covered by the runtime-ignore cleanup plan unless code review proves otherwise.

## Tasks

### Task 1: Add raw export fields

- [ ] Add `MinGold` and `MaxGold` to the raw loot-table export model.
- [ ] Populate the two fields from `LootTable.MinGold` and `LootTable.MaxGold` in the loot-table listener.
- [ ] Update `src/tools/ExportSurface/field-coverage.json` so `MinGold` and `MaxGold` are captured by the loot-table export path.

### Task 2: Add clean database representation

- [ ] Add clean loot gold range fields in `src/erenshor/application/processor/writer.py`.
- [ ] Map raw `MinGold` and `MaxGold` through the processor.
- [ ] Preserve existing per-item drop probability rows without duplicating gold as an item drop.

### Task 3: Verify loot gold output

- [ ] Add or update a focused processor/export test that proves clean gold range fields are populated from raw rows.
- [ ] Run the focused test.
- [ ] Run `uv run erenshor -V playtest extract export`.
- [ ] Run `uv run erenshor -V playtest extract code-facts`.
- [ ] Run `uv run erenshor -V playtest extract build`.
- [ ] Run affected tests and `uv run pytest` if schema or processor code changes.

## Acceptance

- Static loot gold ranges are available in the clean database.
- Runtime roll state remains excluded with code-backed reasons.
- `field-coverage.json` no longer marks `MinGold` or `MaxGold` ignored.
- Playtest export/build and focused tests pass.
