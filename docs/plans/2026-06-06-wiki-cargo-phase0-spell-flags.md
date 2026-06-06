# Cargo Phase 0: Export wiki-relevant Spell flags — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export the four wiki-relevant `Spell.cs` booleans (`GrantInvisibility`, `CannotInterrupt`, `JoltSpell`, `NoResonate`) end-to-end so the database, the `Module:Erenshor/Data/Spells` Lua module, and (later) the `Spells` Cargo table all carry them in one pass.

**Architecture:** A spell field flows through a fixed chain: Unity C# record (`SpellRecord`) + listener (`SpellListener`) write the **raw** DB; the Python processor copies raw→clean with automatic PascalCase→snake_case renaming (no per-field code); the **clean** schema (`writer.py`), the spell entity, and the spell repository read it; the Lua generator emits it. We add the four columns at every layer except the processor (which auto-renames) and surface them as booleans in the Lua data module.

**Tech Stack:** C# (Unity export, SQLite-net records), Python 3 (Typer CLI, Pydantic entities, sqlite3 processor), Lua data modules, `uv` + `pytest` + `ruff` + `mypy`.

**Scope note:** This is Phase 0 of the Cargo data architecture spec (`docs/plans/2026-06-04-wiki-cargo-data-architecture.md` §13). It is a prerequisite that must land before the Cargo `Spells` table (Phase 2) so that table includes these columns from the start. `ForHardEncounters` and `HardcodedUseCase` are deliberately NOT exported (NPC-AI/engine internals with no display value).

**Field name mapping (used throughout):**

| C# (`Spell`) | raw column | clean column | entity field | Lua key |
|---|---|---|---|---|
| `GrantInvisibility` | `GrantInvisibility` | `grant_invisibility` | `grant_invisibility` | `grantInvisibility` |
| `CannotInterrupt` | `CannotInterrupt` | `cannot_interrupt` | `cannot_interrupt` | `cannotInterrupt` |
| `JoltSpell` | `JoltSpell` | `jolt_spell` | `jolt_spell` | `jolt` |
| `NoResonate` | `NoResonate` | `no_resonate` | `no_resonate` | `noResonate` |

---

## File Structure

- `src/erenshor/domain/entities/spell.py` — add four `int | None` fields (clean-DB booleans stored as 0/1).
- `src/erenshor/application/wiki_lua/spells.py` — add four `(lua_key, attr)` tuples to `_BOOL_FIELD_MAP` so the Lua data module emits them.
- `tests/unit/application/wiki_lua/test_spells_module.py` — add a unit test proving the Lua record carries the flags.
- `src/erenshor/application/processor/writer.py` — add four `INTEGER` columns to the clean `spells` `CREATE TABLE`.
- `src/erenshor/infrastructure/database/repositories/spells.py` — add four columns to `_SPELL_COLUMNS` so the repo reads them into the entity.
- `src/Assets/Editor/Database/SpellRecord.cs` — add four `bool` properties (raw schema).
- `src/Assets/Editor/ExportSystem/AssetScanner/Listener/SpellListener.cs` — map four properties from `spell.<Field>`.
- (No change to `src/erenshor/application/processor/entities.py`: `process_spells` does `SELECT * FROM Spells` + `_rename_cols` auto snake_case + `writer.insert_spells`, so new columns propagate automatically once the raw record and clean schema have them.)

---

## Task 1: Spell entity fields + Lua data emission (TDD)

**Files:**
- Modify: `src/erenshor/domain/entities/spell.py` (after the `worn_effect` field, ~line 136)
- Modify: `src/erenshor/application/wiki_lua/spells.py` (`_BOOL_FIELD_MAP`)
- Test: `tests/unit/application/wiki_lua/test_spells_module.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/application/wiki_lua/test_spells_module.py`:

```python
def test_spell_record_emits_wiki_relevant_flags() -> None:
    spell = make_spell(
        stable_key="spell:test_invis",
        grant_invisibility=1,
        cannot_interrupt=1,
        jolt_spell=1,
        no_resonate=1,
    )

    data = build_spells_data([spell], {spell.stable_key: []})
    record = data["spells"][spell.stable_key]

    assert record["grantInvisibility"] is True
    assert record["cannotInterrupt"] is True
    assert record["jolt"] is True
    assert record["noResonate"] is True


def test_spell_record_omits_unset_flags() -> None:
    spell = make_spell(
        stable_key="spell:test_plain",
        grant_invisibility=0,
        cannot_interrupt=0,
        jolt_spell=0,
        no_resonate=0,
    )

    record = build_spells_data([spell], {spell.stable_key: []})["spells"][spell.stable_key]

    assert "grantInvisibility" not in record
    assert "cannotInterrupt" not in record
    assert "jolt" not in record
    assert "noResonate" not in record
```

(The second test pins the existing `_put_bool` convention — falsy flags are omitted, not emitted as `false`. Verify this matches `_put_bool` in `spells.py`; if `_put_bool` emits `False` for 0, change the second test to assert `is False` instead, and keep it.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/application/wiki_lua/test_spells_module.py -k flags -v`
Expected: FAIL — `make_spell(grant_invisibility=1, ...)` raises a Pydantic validation error (unexpected keyword / field) OR the records lack the keys (`KeyError`).

- [ ] **Step 3: Add the entity fields**

In `src/erenshor/domain/entities/spell.py`, immediately after the `worn_effect` field:

```python
    # Casting / proc flags (wiki-relevant booleans)
    grant_invisibility: int | None = Field(default=None, description="Makes the target invisible (boolean)")
    cannot_interrupt: int | None = Field(default=None, description="Casting cannot be interrupted (boolean)")
    jolt_spell: int | None = Field(default=None, description="Jolts/interrupts the target on resolve (boolean)")
    no_resonate: int | None = Field(default=None, description="Suppresses the resonate proc chain (boolean)")
```

- [ ] **Step 4: Add the Lua bool-map entries**

In `src/erenshor/application/wiki_lua/spells.py`, append to the `_BOOL_FIELD_MAP` tuple list (where `("taunt", "taunt_spell")` and `("crowdControl", "crowd_control_spell")` live):

```python
    ("grantInvisibility", "grant_invisibility"),
    ("cannotInterrupt", "cannot_interrupt"),
    ("jolt", "jolt_spell"),
    ("noResonate", "no_resonate"),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/application/wiki_lua/test_spells_module.py -k flags -v`
Expected: PASS (both tests).

- [ ] **Step 6: Static checks**

Run: `uv run ruff check src/erenshor/domain/entities/spell.py src/erenshor/application/wiki_lua/spells.py tests/unit/application/wiki_lua/test_spells_module.py && uv run mypy src`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/erenshor/domain/entities/spell.py src/erenshor/application/wiki_lua/spells.py tests/unit/application/wiki_lua/test_spells_module.py
git commit -m "feat(pipeline): surface wiki-relevant spell flags in Lua data"
```

---

## Task 2: Clean DB schema + repository read

**Files:**
- Modify: `src/erenshor/application/processor/writer.py` (clean `spells` `CREATE TABLE`, after `worn_effect`)
- Modify: `src/erenshor/infrastructure/database/repositories/spells.py` (`_SPELL_COLUMNS`, after `s.worn_effect`)

Schema plumbing is verified end-to-end in Task 4 (after a rebuild). It carries no behavior on its own, so there is no separate unit test here.

- [ ] **Step 1: Add the clean-schema columns**

In `src/erenshor/application/processor/writer.py`, in the `spells` `CREATE TABLE`, immediately after the `worn_effect INTEGER,` line:

```sql
    grant_invisibility                  INTEGER,
    cannot_interrupt                    INTEGER,
    jolt_spell                          INTEGER,
    no_resonate                         INTEGER,
```

- [ ] **Step 2: Add the repository SELECT columns**

In `src/erenshor/infrastructure/database/repositories/spells.py`, in `_SPELL_COLUMNS`, immediately after the `s.worn_effect,` line:

```sql
    s.grant_invisibility,
    s.cannot_interrupt,
    s.jolt_spell,
    s.no_resonate,
```

- [ ] **Step 3: Static check**

Run: `uv run ruff check src/erenshor/application/processor/writer.py src/erenshor/infrastructure/database/repositories/spells.py && uv run mypy src`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add src/erenshor/application/processor/writer.py src/erenshor/infrastructure/database/repositories/spells.py
git commit -m "feat(pipeline): add spell flag columns to clean schema and repo"
```

---

## Task 3: Unity export (raw schema + listener)

**Files:**
- Modify: `src/Assets/Editor/Database/SpellRecord.cs` (after the `WornEffect` property, in the Special Mechanics section)
- Modify: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/SpellListener.cs` (after the `WornEffect = spell.WornEffect,` mapping)

C# export code is not unit-tested in this repo; it is verified by running the export in Task 4 and inspecting the raw DB.

- [ ] **Step 1: Add the record properties**

In `src/Assets/Editor/Database/SpellRecord.cs`, immediately after `public bool WornEffect { get; set; } // From Spell.WornEffect`:

```csharp
    public bool GrantInvisibility { get; set; } // From Spell.GrantInvisibility
    public bool CannotInterrupt { get; set; } // From Spell.CannotInterrupt
    public bool JoltSpell { get; set; } // From Spell.JoltSpell
    public bool NoResonate { get; set; } // From Spell.NoResonate
```

- [ ] **Step 2: Add the listener mappings**

In `src/Assets/Editor/ExportSystem/AssetScanner/Listener/SpellListener.cs`, immediately after `WornEffect = spell.WornEffect,`:

```csharp
            GrantInvisibility = spell.GrantInvisibility,
            CannotInterrupt = spell.CannotInterrupt,
            JoltSpell = spell.JoltSpell,
            NoResonate = spell.NoResonate,
```

- [ ] **Step 3: Commit**

```bash
git add src/Assets/Editor/Database/SpellRecord.cs src/Assets/Editor/ExportSystem/AssetScanner/Listener/SpellListener.cs
git commit -m "feat(export): export wiki-relevant spell flags to raw DB"
```

---

## Task 4: Regenerate data + end-to-end verification

**Files:** none (commands + generated artifacts). Requires the Unity editor/game files for the `main` variant (see `refreshing-game-data` and `unity-export-system` skills).

- [ ] **Step 1: Re-export the raw DB**

Run: `uv run erenshor extract export`
Expected: exit 0; `variants/main/erenshor-main-raw.sqlite` rewritten.

- [ ] **Step 2: Verify the raw DB has the columns**

Run: `sqlite3 variants/main/erenshor-main-raw.sqlite "SELECT COUNT(*) FROM pragma_table_info('Spells') WHERE name IN ('GrantInvisibility','CannotInterrupt','JoltSpell','NoResonate');"`
Expected: `4`.

- [ ] **Step 3: Rebuild the clean DB**

Run: `uv run erenshor extract build`
Expected: exit 0; `variants/main/erenshor-main.sqlite` rewritten.

- [ ] **Step 4: Verify the clean DB columns and that the flags carry real data**

Run:
```bash
sqlite3 variants/main/erenshor-main.sqlite "SELECT COUNT(*) FROM pragma_table_info('spells') WHERE name IN ('grant_invisibility','cannot_interrupt','jolt_spell','no_resonate');"
sqlite3 variants/main/erenshor-main.sqlite "SELECT 'grant_invisibility', COUNT(*) FROM spells WHERE grant_invisibility=1 UNION ALL SELECT 'cannot_interrupt', COUNT(*) FROM spells WHERE cannot_interrupt=1 UNION ALL SELECT 'jolt_spell', COUNT(*) FROM spells WHERE jolt_spell=1 UNION ALL SELECT 'no_resonate', COUNT(*) FROM spells WHERE no_resonate=1;"
```
Expected: first query `4`. Second query: per-flag truthy counts. `grant_invisibility` should match the known invisibility spell(s) (≥1). If any flag is `0` across all spells, confirm against `Spell.cs` usage that it is genuinely unused on `SimUsable` spells before accepting — a flag that is set in-game but `0` everywhere indicates a broken export mapping (re-check Task 3).

- [ ] **Step 5: Regenerate the Lua data module and confirm the keys appear**

Run the project's spell Lua-module generation (the command that writes `Module:Erenshor/Data/Spells.lua` — see `wiki` CLI group), then:
```bash
grep -c -E "grantInvisibility|cannotInterrupt|noResonate|jolt" <generated Spells.lua path>
```
Expected: ≥1 (the generated module now carries the flags for spells that have them). If the generator writes to the wiki dev fixtures or a variant output dir, inspect that path.

- [ ] **Step 6: Regenerate golden baselines and review**

Run: `uv run erenshor golden capture`
Then review the diff: the only changes should be the four new spell fields appearing on spells that have them. Run `git diff -- tests/golden` and confirm no unrelated churn.

- [ ] **Step 7: Targeted test + static gate**

Run: `uv run pytest tests/unit/application/wiki_lua -q && uv run ruff check src tests && uv run mypy src`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add variants/main/erenshor-main.sqlite tests/golden
git commit -m "chore(pipeline): regenerate data with spell flags"
```

(Note: the `variants/main/*.sqlite` databases are gitignored per `AGENTS.md`; if `git add` reports nothing for them, that is expected — only `tests/golden` and any tracked generated Lua module are committed. Adjust the `git add` to the actually-tracked artifacts.)

---

## Self-Review

**Spec coverage:** This plan implements spec §5.2's Phase 0 requirement (export `GrantInvisibility`, `CannotInterrupt`, `JoltSpell`, `NoResonate`; skip `ForHardEncounters`/`HardcodedUseCase`) and the §13 step-0 export chain (`SpellRecord.cs` → `SpellListener.cs` → `writer.py` → `repositories/spells.py` → `spell.py` → `wiki_lua/spells.py`). The processor (`entities.py`) is intentionally untouched (verified: `process_spells` auto-renames via `_rename_cols`). The `Spells` Cargo table itself is Phase 2, not here.

**Placeholder scan:** No TBD/TODO. The one conditional is Step 1's note about `_put_bool`'s falsy convention — the engineer confirms it against the actual helper and keeps whichever assertion matches; both branches are spelled out.

**Type consistency:** Field names are consistent across all layers via the mapping table in the header (`grant_invisibility`/`grantInvisibility` etc.). Entity fields are `int | None` matching the existing boolean convention (`worn_effect`, `taunt_spell`). Lua keys (`grantInvisibility`, `cannotInterrupt`, `jolt`, `noResonate`) match the test assertions in Task 1.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-06-wiki-cargo-phase0-spell-flags.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. (Note: Task 4 needs the Unity editor + `main` game files; it cannot run in a sandbox without them.)
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
