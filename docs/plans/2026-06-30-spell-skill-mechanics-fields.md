---
title: Spell and Skill Mechanics Fields
type: plan
status: active
created: 2026-06-30
---

# Spell and Skill Mechanics Fields

**Goal:** Export omitted scalar mechanics fields from spells and skills.

**Scope:** This plan covers `Skill.SkillCanCrit`, `Spell.ArmorPenPercent`, `Spell.LevelScaledManaRestoration`, and `Spell.ShapeshiftForm`.

## Tasks

### Task 1: Add raw export fields

- [ ] Add `SkillCanCrit` to `src/Assets/Editor/Database/SkillRecord.cs`.
- [ ] Populate `SkillCanCrit` in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/SkillListener.cs`.
- [ ] Add `ArmorPenPercent`, `LevelScaledManaRestoration`, and `ShapeshiftForm` to `src/Assets/Editor/Database/SpellRecord.cs`.
- [ ] Populate the three spell fields in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/SpellListener.cs`.
- [ ] Update `src/tools/ExportSurface/field-coverage.json` so the four fields are captured by their listeners.

### Task 2: Add clean database fields

- [ ] Add clean `skills.skill_can_crit` in `src/erenshor/application/processor/writer.py`.
- [ ] Add clean spell columns for armor penetration percent, level-scaled mana restoration, and shapeshift form.
- [ ] Map the raw fields in the skill and spell processing paths.

### Task 3: Verify spell and skill output

- [ ] Add or update focused processor/export tests that prove the clean columns are populated from raw rows.
- [ ] Run the focused tests.
- [ ] Run `uv run erenshor -V playtest extract export`.
- [ ] Run `uv run erenshor -V playtest extract code-facts`.
- [ ] Run `uv run erenshor -V playtest extract build`.
- [ ] Run affected tests and `uv run pytest` if schema or processor code changes.

## Acceptance

- The raw `Skills` and `Spells` tables contain the scoped fields.
- The clean `skills` and `spells` tables contain corresponding columns.
- `field-coverage.json` has no ignored entries for these four fields.
- Playtest export/build and focused tests pass.
