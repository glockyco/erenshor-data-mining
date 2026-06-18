# Adventure Guide Stable-Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace main's current BepInEx AdventureGuide rewrite with the stable Lunaris implementation, preserving every non-AdventureGuide change on main.

**Architecture:** The stable AG is a native Lunaris plugin (`[LunarisPlugin]`, Lunaris-provided ImGui, embeds raw `quest-guide.json`). main's AG is a BepInEx rewrite (`[BepInPlugin]`, private `cimgui.dll`, embeds compiled `guide.json`). We swap the mod source tree, the mod's test surface, and add first-class Lunaris-loader support to the `mod` CLI. The guide-data pipeline is untouched: main already produces `quest_guides/quest-guide.json` with the identical schema (`_version: 5`) the stable AG consumes, so no data work is needed.

**Tech Stack:** C# / netstandard2.1 (mod), Python / Typer (CLI), Lunaris loader, Newtonsoft.Json, ImGui.NET (Lunaris-provided), pytest (Python tests), dotnet (C# build).

---

## Context & Key Findings (read before starting)

- **Source of the stable AG:** branch `adventure-guide-thunderstore-lunaris` (the worktree this plan was authored from). It is 29 commits ahead of merge-base `bfa55558`. Treat it as a read-only source; pull files with `git checkout adventure-guide-thunderstore-lunaris -- <path>`. **Never merge this branch** — it is 682 commits behind main.
- **Base:** current `main` (worktree `adventure-guide-stable-port`, branched off main). All work lands here.
- **Data compatibility (verified):** `quest_guides/quest-guide.json` on main and on the branch share an identical schema — top-level keys `_chain_groups, _character_quest_unlocks, _character_spawns, _version, _zone_lines, _zone_lookup, quests`; `_version: 5` on both; quest keys `acceptance, acquisition, chain, completion, db_name, description, display_name, flags, level_estimate, quest_type, required_items, rewards, stable_key, steps, zone_context`; step keys `action, description, keyword, level_estimate, order, target_key, target_name, target_type`. main has 176 quests vs the branch's 175 (fresher data, picked up for free). The stable AG's `GuideWrapper`/`QuestEntry` bind exactly these. Task 9 still deep-validates this at runtime.
- **main's AG is BepInEx**, embeds the **compiled** `guide.json` (only the rewrite reads it; leaving `guide.json` produced is harmless). The stable AG embeds the **raw** `quest-guide.json`. No pipeline change.
- **CLI:** main's `src/erenshor/cli/commands/mod.py` is BepInEx-only (`ModInfo.bepinex_dlls`, ILRepack, deploy to `BepInEx/plugins`). The branch added a clean loader abstraction (`loader: "lunaris"`, `lunaris_dlls`, per-loader deploy). We port that abstraction, improved (see Design Decisions).
- **Do NOT port** the branch's `lefthook.yml`, `commitlint.config.cjs`, `.husky/pre-commit`, `package.json`, `pnpm-lock.yaml`, `src/mods/run-csharpier.sh`. main already has all of these (its `lefthook.yml` runs csharpier on `src/mods/**/*.cs`).
- **csproj generator** (`src/erenshor/infrastructure/csproj_generator.py`) only generates IDE/LSP helper csprojs + the root solution via `discover_mod_projects`. The mod csproj is hand-maintained. Removing main's `AdventureGuide.Tests` C# project removes it from the discovered solution automatically.

## Design Decisions & Improvements

1. **First-class loader field (keep).** `ModInfo.loader: "lunaris" | "bepinex"` (absent ⇒ bepinex) with `lunaris_dlls`. This is the branch's design and is clean; keep it.
2. **IMPROVEMENT — no machine-specific paths.** The branch's `_find_lunaris_dll`/`_find_lunaris_shared_lib` hardcode `~/Projects/Lunaris/...`. Replace with: (a) the game's Lunaris install (`game_path`) where available, (b) a configured `lunaris_lib_dir` resolved through the existing config system (`resolved_*` pattern, per AGENTS.md), (c) env override (`ERENSHOR_LUNARIS_DLL` / `ERENSHOR_LUNARIS_LIB_DIR`). No `~/Projects` literals in code. (Task 5.)
3. **IMPROVEMENT — 0Harmony provenance.** The stable AG needs `0Harmony.dll` in `lib/` at compile time. main's `setup` copies it from `BepInEx/core`, which a Lunaris-only install may lack. `setup` for a Lunaris mod must source `0Harmony.dll` from the configured Lunaris lib dir (Lunaris bundles Harmony), falling back to BepInEx if present. (Task 5.)
4. **No private ImGui binaries.** The stable AG must NOT ship `resources/cimgui.dll` or reference `ImGui.NET` as a NuGet package; it uses Lunaris-provided `ImGui.NET.dll`/`cimgui`. The branch's csproj already does this — bring it verbatim.
5. **Test surface swap (lightweight by design).** Delete main's `src/mods/AdventureGuide/tests/AdventureGuide.Tests/` (it tests the deleted rewrite) and bring the stable AG's Python tests (`tests/unit/mods/test_adventure_guide_*.py`). Do NOT recreate a C# test project: main's harness needed a `CopyBepInExRuntime` target and `GeneratePathProperty` shims just to JIT-load types — a setup more complex than the code it guarded. The mod's Unity/ImGui-coupled behavior is verified by the in-game smoke (Task 8 Step 2); the JSON data contract by a lightweight Python schema test (Task 8 Step 1). That boundary is deliberate, not an oversight.
6. **Rewrite design docs are historical.** Leave main's `docs/superpowers/specs/*adventure-guide*` and related plan docs in place (project history). The mod's own `README.md`/`AGENTS.md` are replaced with the stable Lunaris versions.
7. **Thunderstore.** Drop the `thunderstore` key from the AG registry entry (AG is Lunaris-only going forward). The published Thunderstore page stays up; that is separate.

## File Structure

**Removed (main's rewrite):**
- `src/mods/AdventureGuide/src/**` (entire rewrite source: `Incremental/`, `Graph/`, `Frontier/`, `Markers/`, `CompiledGuide/`, `Diagnostics/`, `Navigation/`, `Resolution/`, `Position/`, `UI/`, `State/`, `Patches/`, `Config/`, `Compat/`, `Plugin.cs`, …)
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/**` (C# test project for the rewrite)
- `src/mods/AdventureGuide/resources/cimgui.dll` (private ImGui — forbidden)
- `src/mods/AdventureGuide/AdventureGuide.csproj` (BepInEx variant; replaced)
- main's AG `README.md`, `AGENTS.md`, `ILRepack.targets`, `nuget.config` if present (replaced/removed per branch tree)

**Added (from `adventure-guide-thunderstore-lunaris`):**
- `src/mods/AdventureGuide/src/**` (stable tree)
- `src/mods/AdventureGuide/AdventureGuide.csproj` (Lunaris variant)
- `src/mods/AdventureGuide/resources/Roboto-Regular.ttf`
- `src/mods/AdventureGuide/vault/**` (`vault.toml`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `icon.png`)
- `src/mods/AdventureGuide/README.md`, `src/mods/AdventureGuide/AGENTS.md` (Lunaris)
- `tests/unit/mods/test_adventure_guide_*.py`

**Modified (on main):**
- `src/erenshor/cli/commands/mod.py` (loader support, AG registry entry, `REQUIRED_DLLS`)
- `src/erenshor/infrastructure/config/schema.py` + `paths.py` (Lunaris lib dir; Task 6)
- `config.toml` (Lunaris lib dir default; Task 6)
- `tests/unit/cli/commands/test_mod.py` (loader behavior)

---

**Commit invariant:** the pre-commit hook runs ruff, `mypy src/`, and `pytest tests/unit` on any staged `*.py`. Any task that stages a `.py` file MUST leave `uv run pytest tests/unit -q` green before committing; tasks staging only non-`.py` files (C#, toml, md) skip the pytest gate. The ported AG Python tests assert the Lunaris/Thunderstore-flipped registry, so they are imported and committed in Task 6 — after the `mod.py` change (Task 4).

### Task 1: Remove main's AdventureGuide rewrite

**Files:**
- Delete: `src/mods/AdventureGuide/` (entire directory; rebuilt from the branch in Task 2)

- [ ] **Step 1: Confirm what is tracked**

Run: `git ls-files src/mods/AdventureGuide | sed 's#/.*##' | sort -u`
Expected: `src/mods/AdventureGuide` entries (src, tests, resources, *.csproj, etc.)

- [ ] **Step 2: Remove the directory**

```bash
git rm -r src/mods/AdventureGuide
```

- [ ] **Step 3: Verify the rest of the tree still references nothing broken**

Run: `grep -rn "AdventureGuide" src/erenshor/cli/commands/mod.py`
Expected: the `adventure-guide` registry entry still references `src/mods/AdventureGuide` (path will be repopulated in Task 2). No other code imports AG.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(mod): remove BepInEx Adventure Guide rewrite"
```

### Task 2: Import the stable Lunaris AdventureGuide tree

**Files:**
- Create (from branch): `src/mods/AdventureGuide/src/**`, `AdventureGuide.csproj`, `resources/Roboto-Regular.ttf`, `vault/**`, `README.md`, `AGENTS.md`, `.gitignore` (if present on branch)

- [ ] **Step 1: Check out the stable AG tree from the source branch**

```bash
git checkout adventure-guide-thunderstore-lunaris -- src/mods/AdventureGuide
```

- [ ] **Step 2: Verify no private ImGui binary and no BepInEx package ref came in**

Run: `ls src/mods/AdventureGuide/resources; grep -nE "cimgui|BepInEx.Core|PackageReference Include=\"ImGui" src/mods/AdventureGuide/AdventureGuide.csproj || echo CLEAN`
Expected: `resources/` contains only `Roboto-Regular.ttf`; grep prints `CLEAN`.

- [ ] **Step 3: Verify the data contract embed**

Run: `grep -n "quest-guide.json\|guide.json" src/mods/AdventureGuide/AdventureGuide.csproj`
Expected: embeds `../../../quest_guides/quest-guide.json` as `AdventureGuide.quest-guide.json` (NOT compiled `guide.json`).

- [ ] **Step 4: Commit**

```bash
git add src/mods/AdventureGuide
git commit -m "feat(mod): add stable Lunaris Adventure Guide"
```

### Task 3: Add a failing test for Lunaris loader support in the CLI

**Files:**
- Test: `tests/unit/cli/commands/test_mod.py`

- [ ] **Step 1: Read the existing test to match style**

Run: `sed -n '1,60p' tests/unit/cli/commands/test_mod.py`

- [ ] **Step 2: Write the failing test**

```python
def test_adventure_guide_uses_lunaris_loader() -> None:
    from erenshor.cli.commands.mod import MODS

    ag = MODS["adventure-guide"]
    assert ag["loader"] == "lunaris"
    assert "thunderstore" not in ag
    assert "ImGui.NET.dll" in ag["lunaris_dlls"]
    assert "Newtonsoft.Json.dll" in ag["lunaris_dlls"]


def test_lunaris_mods_deploy_to_plugins_not_bepinex(tmp_path) -> None:
    from erenshor.cli.commands.mod import _get_deploy_target_dir

    target, label, copy_pdb = _get_deploy_target_dir(
        "adventure-guide", tmp_path, scripts=False
    )
    assert target == tmp_path / "plugins"
    assert copy_pdb is False
    assert "Lunaris" in label
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/unit/cli/commands/test_mod.py -q`
Expected: FAIL — `KeyError: 'loader'` / `_get_deploy_target_dir` not defined.

### Task 4: Port the Lunaris loader support onto main's mod.py

**Files:**
- Modify: `src/erenshor/cli/commands/mod.py`

Reference implementation: `git show adventure-guide-thunderstore-lunaris:src/erenshor/cli/commands/mod.py`. Apply these changes onto main's file (do NOT copy the whole file — main is 682 commits downstream):

- [ ] **Step 1: Extend `ModInfo`** (after `bepinex_dlls`):

```python
    loader: NotRequired[str]
    lunaris_dlls: NotRequired[list[str]]
```

- [ ] **Step 2: Flip the `adventure-guide` registry entry** to:

```python
    "adventure-guide": {
        "dir": "src/mods/AdventureGuide",
        "name": "Adventure Guide",
        "dll_name": "AdventureGuide.dll",
        "loader": "lunaris",
        "bepinex_dlls": ["0Harmony.dll"],
        "lunaris_dlls": [
            "ImGui.NET.dll",
            "Newtonsoft.Json.dll",
            "System.Numerics.Vectors.dll",
        ],
    },
```

- [ ] **Step 3: Extend `REQUIRED_DLLS`** with the modules the stable AG references:

```python
    "UnityEngine.IMGUIModule.dll",
    "UnityEngine.TextRenderingModule.dll",
    "UnityEngine.AIModule.dll",
    "UnityEngine.PhysicsModule.dll",
```
(Merge with the existing list; do not duplicate entries already present.)

- [ ] **Step 4: Add `_get_lunaris_plugins_dir` and `_get_deploy_target_dir`** (verbatim from the reference): `_get_lunaris_plugins_dir` returns `game_path / "plugins"`; `_get_deploy_target_dir(mod_id, game_path, *, scripts)` returns `(plugins, "Lunaris plugins", False)` for lunaris loader (raising if `scripts`), else the BepInEx branch.

- [ ] **Step 5: Rewrite `deploy`** to compute the target per-mod via `_get_deploy_target_dir` inside the loop and gate `--scripts` for lunaris mods (verbatim from the reference diff).

- [ ] **Step 6: Run the Task 3 tests to verify they pass**

Run: `uv run pytest tests/unit/cli/commands/test_mod.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/erenshor/cli/commands/mod.py tests/unit/cli/commands/test_mod.py
git commit -m "feat(cli): add Lunaris loader support for mod build/deploy"
```

### Task 5: Configure Lunaris lib sourcing (no machine-specific paths)

**Files:**
- Modify: `src/erenshor/infrastructure/config/schema.py`, `src/erenshor/infrastructure/config/paths.py` (or wherever `resolved_*` path accessors live — confirm by reading)
- Modify: `config.toml`
- Modify: `src/erenshor/cli/commands/mod.py` (`setup` Lunaris branch + `_find_lunaris_*`)
- Test: `tests/unit/infrastructure/config/test_schema.py`

- [ ] **Step 1: Read the config plumbing**

Run: `sed -n '1,200p' src/erenshor/infrastructure/config/schema.py` and `sed -n '1,120p' src/erenshor/infrastructure/config/paths.py`
Identify the `resolved_*` pattern and how a new optional path field is added + resolved (`$REPO_ROOT` expansion).

- [ ] **Step 2: Write a failing test** for a resolved Lunaris lib dir (mirror an existing resolved-path test in `test_schema.py`). Assert the new field defaults sensibly and resolves `$REPO_ROOT`/`~` correctly.

- [ ] **Step 3: Run it to confirm it fails.**

- [ ] **Step 4: Add the config field** (e.g. `[mods]` → `lunaris_lib_dir`) with a `resolved_lunaris_lib_dir` accessor following the established pattern; add the default to `config.toml` with a comment that it points at the Lunaris build/Embeds output that provides `Lunaris.dll`, `ImGui.NET.dll`, `Newtonsoft.Json.dll`, `System.Numerics.Vectors.dll`, `0Harmony.dll`.

- [ ] **Step 5: Rewrite `_find_lunaris_dll` / `_find_lunaris_shared_lib`** to resolve from, in order: env override (`ERENSHOR_LUNARIS_DLL`/`ERENSHOR_LUNARIS_LIB_DIR`) → `game_path` → `resolved_lunaris_lib_dir`. Remove all `~/Projects/Lunaris` literals.

- [ ] **Step 6: Update `setup`'s Lunaris branch** to also stage `0Harmony.dll` from the resolved Lunaris lib dir when a BepInEx core copy is unavailable (improvement #3).

- [ ] **Step 7: Run config + mod tests to verify pass.**

Run: `uv run pytest tests/unit/infrastructure/config tests/unit/cli/commands/test_mod.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/erenshor/infrastructure/config config.toml src/erenshor/cli/commands/mod.py tests/unit/infrastructure/config
git commit -m "feat(config): resolve Lunaris build libraries from config not hardcoded paths"
```

### Task 6: Port the AdventureGuide Python tests

**Files:**
- Create (from branch): `tests/unit/mods/test_adventure_guide_*.py`

- [ ] **Step 1: Bring the stable AG Python tests**

```bash
git checkout adventure-guide-thunderstore-lunaris -- tests/unit/mods
```

- [ ] **Step 2: Confirm the files arrived**

Run: `ls tests/unit/mods/`
Expected: `test_adventure_guide_font.py`, `test_adventure_guide_lunaris.py`, `test_adventure_guide_quest_list.py`, `test_adventure_guide_renderer.py`, `test_adventure_guide_shortcuts.py`, `test_adventure_guide_style.py`, `test_adventure_guide_vault.py`.

- [ ] **Step 3: Run them — all should pass now**

Run: `uv run pytest tests/unit/mods -q`
Expected: PASS. `test_adventure_guide_vault.py`'s Thunderstore-removal + Lunaris assertions hold because Task 4 flipped the registry; the renderer/shortcut/style/quest-list/font tests assert the AG source brought in Task 2. If anything fails, STOP — a prior task is incomplete.

- [ ] **Step 4: Confirm the whole unit suite is green before committing**

Run: `uv run pytest tests/unit -q`
Expected: PASS (this is exactly what the pre-commit hook runs on the staged `.py` files).

- [ ] **Step 5: Commit**

```bash
git add tests/unit/mods
git commit -m "test(mod): port stable Adventure Guide tests"
```

### Task 7: Set up libs and build the mod

**Files:** none (verification task)

- [ ] **Step 1: Stage game + Lunaris DLLs into the mod lib/**

Run: `uv run erenshor mod setup`
Expected: copies game Unity DLLs + `Lunaris.dll` + `ImGui.NET.dll` + `Newtonsoft.Json.dll` + `System.Numerics.Vectors.dll` + `0Harmony.dll` into `src/mods/AdventureGuide/lib/`. No missing-DLL errors.

- [ ] **Step 2: Build the mod**

Run: `uv run erenshor mod build --mod adventure-guide`
Expected: builds `bin/Debug/netstandard2.1/AdventureGuide.dll` with only the known tolerated warnings (`MSB3243` for `System.Numerics.Vectors`; `MSB3277` for `System.Net.Http` / `System.IO.Compression`). No errors.

- [ ] **Step 3: Confirm the output is a single standalone DLL (no merged/extra deps)**

Run: `ls bin/Debug/netstandard2.1/` from the mod dir
Expected: `AdventureGuide.dll` (+ `.pdb`/`.xml`); no bundled `ImGui.NET.dll`/`Newtonsoft.Json.dll`/`cimgui.dll`.

### Task 8: Deep data validation + runtime smoke (Lunaris)

**Files:** none (verification task — the gating data check the schema diff implied)

- [ ] **Step 1: Validate embedded data deserializes with real field content**

Confirm the embedded `quest-guide.json` is main's current copy and the stable AG reads it. Quick deserialization spot-check without the game:
```bash
python3 - <<'PY'
import json, pathlib
d = json.loads(pathlib.Path("quest_guides/quest-guide.json").read_text())
assert d["_version"] == 5, d["_version"]
q = d["quests"][0]
for k in ("db_name","display_name","steps","level_estimate","zone_context"):
    assert k in q, k
s = q["steps"][0]
for k in ("action","target_type","target_key","order"):
    assert k in s, k
print("quests:", len(d["quests"]), "sample:", q["db_name"])
PY
```
Expected: prints quest count (~176) and a sample db_name; no assertion error. (This proves the field-level contract the stable AG's `GuideWrapper`/`QuestEntry`/`QuestStep` bind.)

- [ ] **Step 2: Deploy to a Lunaris install and smoke-test**

```bash
ERENSHOR_GAME_PATH="<path to Erenshor or Erenshor Playtest>" \
  uv run erenshor mod deploy --mod adventure-guide
```
Then launch and verify in-game (per `vault/AGENTS.md` and the renderer history): no `No texture data provided to LoadRawTextureData`; guide opens (`L`), tracker toggles (`K`), Roboto renders, arrow + world markers render, quest list shows ~176 quests, a known quest's steps/objectives display correct text, UI-scale change rebuilds the atlas cleanly, inventory shortcuts are not swallowed.

- [ ] **Step 3: No commit** (verification only). If Step 1 or 2 reveals drift, STOP and add a data-adapter task before proceeding.

### Task 9: Reconcile docs and finalize

**Files:**
- Verify: `src/mods/AdventureGuide/README.md`, `AGENTS.md`, `vault/**` (came from the branch in Task 2)
- Modify (if needed): root `AGENTS.md` skill table / mod-development skill references that describe AG as the BepInEx rewrite

- [ ] **Step 1: Scan for stale AG references on main that now describe the removed rewrite**

Run: `search` for `CompiledGuide|reactive|IncrementalEngine|guide.json` in `.agent/skills/mod-development` and any AG-facing skill/doc that gives build/run instructions (not the historical `docs/superpowers/specs`, which stay).
Fix any that give now-wrong build/run guidance (e.g. BepInEx deploy, compiled-guide embedding) to match the Lunaris reality.

- [ ] **Step 2: Confirm the mod-development / mod-pipeline skills mention the Lunaris loader path** if they enumerate loaders; update minimally if they assert BepInEx-only.

- [ ] **Step 3: Commit (if changes)**

```bash
git add -A
git commit -m "docs: align Adventure Guide guidance with the Lunaris port"
```

### Task 10: Full verification

**Files:** none

- [ ] **Step 1: Full unit suite**

Run: `uv run pytest tests/unit -q`
Expected: all pass (the prior main baseline was 937 passed / 13 skipped; the AG C# test project removal drops C# tests not run by pytest; the AG Python tests are added). No failures.

- [ ] **Step 2: Lint/type gates (what the pre-commit hook runs)**

Run: `uv run ruff check src/ && uv run mypy src/`
Expected: clean.

- [ ] **Step 3: C# format check**

Run: `bash src/mods/run-csharpier.sh src/mods/AdventureGuide/src` (or the repo's check variant)
Expected: no reformatting needed (the branch tree was already formatted).

- [ ] **Step 4: Golden review (data-affecting?)**

The port does not change the data pipeline, so golden baselines should be unaffected. Run `uv run erenshor golden capture` only if `git status` shows golden-relevant changes; review any diff. Expected: no diffs.

## Self-Review Checklist (author runs before handoff)

1. **Spec coverage:** loader swap (T1-T2), CLI Lunaris support (T3-T4), config no-hardcoded-paths + 0Harmony (T5), test swap (T1, T6), build (T7), data validation + runtime (T8), docs (T9), full verify (T10). ✓
2. **Placeholders:** none — file moves use exact `git checkout` commands; mod.py changes are quoted; config task references the real files to read first.
3. **Type/name consistency:** `loader`, `lunaris_dlls`, `_get_deploy_target_dir`, `_get_lunaris_plugins_dir`, `_find_lunaris_dll`, `_find_lunaris_shared_lib`, `resolved_lunaris_lib_dir` used consistently.
4. **Preserve-everything-else:** only `src/mods/AdventureGuide/**`, `tests/unit/mods/test_adventure_guide_*`, `mod.py`, config files, and minimal docs are touched. No wiki/export/pipeline/maps files. ✓

## Risks

- **Lunaris compile-time DLLs availability.** Building the stable AG requires `Lunaris.dll` + `ImGui.NET.dll` + `Newtonsoft.Json.dll` + `System.Numerics.Vectors.dll` + `0Harmony.dll` on disk. If the environment lacks a Lunaris build/Embeds dir, `mod setup` (Task 7) fails fast with a clear message — resolve by setting `lunaris_lib_dir` / env override.
- **Data drift (mitigated).** Task 8 Step 1 is a lightweight structural field-contract check (top-level / quest / step keys + `_version: 5`). If main's `quest-guide.json` diverges it fails there; the in-game smoke (Step 2) confirms the actual C# Newtonsoft binding. If drift appears, stop and add an adapter.
- **No executable C# behavioral coverage (deliberate).** The stable mod's logic is Unity/ImGui-coupled; a dotnet harness to exercise it would be more complex than the implementation — the wrong-track signal. The rewrite's diagnostics/incident bundles, reactive markers, and compiled-guide perf are also intentionally dropped. Behavior is guarded by the in-game smoke test, not unit tests.
