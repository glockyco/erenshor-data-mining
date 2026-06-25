---
title: Repo history cleanup plan
type: plan
status: implemented
created: 2026-04-03
archived: 2026-06-25
parent:
---

# Repo history cleanup plan

## Goal
Purge obsolete large files from git history, stop tracking generated Adventure Guide graph data entirely, preserve only the newest `tests/golden/**` baselines in git, and leave `.gitignore` unchanged.

## Decisions already made
This plan reflects the requested scope exactly:

- Remove and purge the old Adventure Guide `quest-guide*.json` files
- Remove any tests that depend on them
- Remove and purge `quest_guides/entity-graph.json`
- Keep the newest `tests/golden/**` files in the repo, but purge their history
- Remove and purge `tests/unit/infrastructure/unity/test_batch_mode.py.bak`
- Purge the already-deleted historical baggage in `Assets/Packages/...`
- Leave the package-manager lockfile situation alone for now
- Do not change `.gitignore`

## Findings summary

### Files to remove from `HEAD` and purge from history

| Path | Why |
| --- | --- |
| `quest_guides/quest-guide.json` | obsolete generated Adventure Guide artifact |
| `quest_guides/quest-guide.golden.json` | obsolete golden comparison artifact |
| `quest_guides/entity-graph.json` | generated graph data should not live in git |
| `src/mods/AdventureGuide/resources/quest-guide.json` | already gone from `HEAD`, still in history |
| `tests/unit/application/guide/test_regression.py` | depends on removed quest-guide JSON files |
| `tests/unit/infrastructure/unity/test_batch_mode.py.bak` | accidental backup file |

### Files to purge from history but keep the newest version in `HEAD`

| Path | Why |
| --- | --- |
| `tests/golden/**` | keep current regression baselines, remove historical churn |

### History-only baggage to purge while rewriting

| Path glob | Why |
| --- | --- |
| `Assets/Packages/SQLitePCLRaw.lib.e_sqlite3.2.1.2/**` | deleted vendor binary baggage |
| `Assets/Packages/Newtonsoft.Json.13.0.3/**` | deleted vendor binary baggage |
| `Assets/Packages/HtmlAgilityPack.1.12.1/**` | deleted vendor binary baggage |
| `Assets/Packages/sqlite-net-pcl.1.9.172/**` | deleted vendor binary baggage |

### Files explicitly staying tracked in `HEAD`

- `tests/golden/**` — current baselines stay
- `mapping.json` — active pipeline inpu
- current map/static and mod assets that are real shipped artifacts
- existing lockfiles — out of scope for this cleanup

## Required design cutover before the history rewrite

`quest_guides/entity-graph.json` is still wired into the Adventure Guide build today, so deleting it safely requires a cutover first.

### Required behavior after cutover

- Adventure Guide must no longer embed a tracked file from `quest_guides/entity-graph.json`
- Adventure Guide must generate its graph locally into an already-ignored path during build
- Build/test must fail clearly if generation prerequisites are missing
- No checked-in fallback graph file should remain

### Recommended local generated path

Use an ignored path under the mod project, for example:

- `src/mods/AdventureGuide/obj/generated/entity-graph.json`

That works with the existing ignore rules because `src/mods/.gitignore` already ignores `obj/`.

## Step-by-step command plan

Below is the command sequence I recommend executing once we move from planning to implementation.

---

## Phase 0: Safety backup before any rewrite

Run from repo root:

```bash
git status --shor
git branch backup/pre-repo-history-cleanup
git tag backup/pre-repo-history-cleanup-2026-04-03
mkdir -p /tmp/erenshor-history-cleanup
cp -R tests/golden /tmp/erenshor-history-cleanup/golden-curren
```

Purpose:

- preserve a branch/tag before rewriting
- preserve the current `tests/golden/**` tree so it can be restored after history is stripped

---

## Phase 1: Remove dead tracked files from `HEAD`

Delete the dead files:

```bash
rm -f quest_guides/quest-guide.json
rm -f quest_guides/quest-guide.golden.json
rm -f quest_guides/entity-graph.json
rm -f tests/unit/application/guide/test_regression.py
rm -f tests/unit/infrastructure/unity/test_batch_mode.py.bak
```

Then update the code/docs during implementation so the mod no longer expects the tracked graph file.
The files that need code changes are:

- `src/mods/AdventureGuide/AdventureGuide.csproj`
- `src/erenshor/cli/commands/guide.py`
- living docs that still describe the checked-in graph/quest-guide flow as curren

After those edits, stage and commit the `HEAD` cleanup:

```bash
git add
  quest_guides
  tests/unit/application/guide/test_regression.py
  tests/unit/infrastructure/unity/test_batch_mode.py.bak
  src/mods/AdventureGuide/AdventureGuide.csproj
  src/erenshor/cli/commands/guide.py
  src/mods/AdventureGuide/README.md

git commit -m "chore(guide): remove tracked guide artifacts"
```

If additional docs are touched, include them in the same commit.

---

## Phase 2: Cut Adventure Guide over to local generated graph data

### Build-time generation command

The generator command itself should become:

```bash
uv run erenshor guide generate --output src/mods/AdventureGuide/obj/generated/entity-graph.json
```

### Verification commands for the cutover

After wiring the `.csproj` to embed the generated file from `obj/generated/entity-graph.json`, verify with:

```bash
uv run erenshor guide generate --output src/mods/AdventureGuide/obj/generated/entity-graph.json
uv run erenshor mod build --mod adventure-guide
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/ --verbosity minimal
```

If there are docs/tests tied to the old tracked path, verify those too.

Then commit the build cutover:

```bash
git add
  src/mods/AdventureGuide/AdventureGuide.csproj
  src/erenshor/cli/commands/guide.py
  src/mods/AdventureGuide/README.md

git commit -m "refactor(mod): generate Adventure Guide graph locally"
```

---

## Phase 3: Rewrite git history

### 3.1 Strip the targeted paths from all history

Run exactly once from repo root:

```bash
git filter-repo --force --invert-paths
  --path quest_guides/quest-guide.json
  --path quest_guides/quest-guide.golden.json
  --path quest_guides/entity-graph.json
  --path src/mods/AdventureGuide/resources/quest-guide.json
  --path tests/unit/application/guide/test_regression.py
  --path tests/unit/infrastructure/unity/test_batch_mode.py.bak
  --path tests/golden
  --path-glob 'Assets/Packages/SQLitePCLRaw.lib.e_sqlite3.2.1.2/**'
  --path-glob 'Assets/Packages/Newtonsoft.Json.13.0.3/**'
  --path-glob 'Assets/Packages/HtmlAgilityPack.1.12.1/**'
  --path-glob 'Assets/Packages/sqlite-net-pcl.1.9.172/**'
```

This intentionally removes `tests/golden/**` from history too.

### 3.2 Restore only the newest `tests/golden/**` tree

```bash
cp -R /tmp/erenshor-history-cleanup/golden-current tests/golden
git add tests/golden
git commit -m "test(pipeline): restore current golden baselines"
```

At this point:

- old guide JSONs are gone from history
- `entity-graph.json` is gone from history and no longer tracked
- old `tests/golden/**` revisions are gone
- the current `tests/golden/**` tree is back in `HEAD`

---

## Phase 4: Verify the rewritten repository

### 4.1 Verify deleted paths are no longer tracked in `HEAD`

```bash
git ls-files
  quest_guides/quest-guide.json
  quest_guides/quest-guide.golden.json
  quest_guides/entity-graph.json
  tests/unit/application/guide/test_regression.py
  tests/unit/infrastructure/unity/test_batch_mode.py.bak
```

Expected result: no output.

### 4.2 Verify `tests/golden/**` is still present in `HEAD`

```bash
readlink tests/golden || true
find tests/golden -type f | head -n 20
```

Expected result: files are present under `tests/golden/**`.

### 4.3 Verify Adventure Guide still builds from local generated graph data

```bash
uv run erenshor mod build --mod adventure-guide
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/ --verbosity minimal
uv run pytest tests/integration/test_golden.py -v
```

### 4.4 Verify the old blobs are gone from reachable history

```bash
git rev-list --objects --all | grep -E 'quest-guide\.json|quest-guide\.golden\.json|entity-graph\.json|test_batch_mode\.py\.bak|tests/golden/'
```

Expected result:

- no old quest-guide/entity-graph/bak hits
- only the newly restored `tests/golden/**` `HEAD` objects should remain reachable

---

## Phase 5: Push the rewritten history

Push rewritten refs:

```bash
git push --force-with-lease --all
git push --force-with-lease --tags
```

Then tell collaborators to re-sync with one of these approaches.

### Safest collaborator instruction

```bash
# easiest: fresh clone
```

### Hard reset alternative for collaborators who know what they are doing

```bash
git fetch --all --prune
git reset --hard origin/main
```

---

## Phase 6: Reclaim local disk space

After the rewrite is pushed, either re-clone or clean the local repo:

```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git count-objects -vH
```

A fresh clone is still the cleanest way to validate the final repo size.

## Planned commits / operations

This work should land as:

1. `chore(guide): remove tracked guide artifacts`
2. `refactor(mod): generate Adventure Guide graph locally`
3. History rewrite operation with `git filter-repo`
4. `test(pipeline): restore current golden baselines`

## What this plan will achieve

After these steps:

- `quest_guides/quest-guide.json` is gone from `HEAD` and history
- `quest_guides/quest-guide.golden.json` is gone from `HEAD` and history
- `quest_guides/entity-graph.json` is gone from `HEAD` and history
- Adventure Guide generates its graph locally into ignored build outpu
- `tests/unit/application/guide/test_regression.py` is gone
- `tests/unit/infrastructure/unity/test_batch_mode.py.bak` is gone
- historical `tests/golden/**` churn is gone
- the newest `tests/golden/**` baselines remain committed in `HEAD`
- `.gitignore` remains unchanged
