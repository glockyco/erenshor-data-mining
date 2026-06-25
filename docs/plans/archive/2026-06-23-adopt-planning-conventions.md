---
title: Adopt Planning Conventions + Migrate docs/plans
type: plan
status: implemented
created: 2026-06-23
archived: 2026-06-25
parent:
---

# Adopt Planning Conventions + Migrate Erenshor's docs/plans — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `skill://executing-plans` (inline, no worktree — standing preference). Steps use `- [x]` checkboxes. **Prerequisite:** the global `omp-plans` CLI + `planning-files` skill must be deployed first (see the omp-agent-setup plan `2026-06-23-omp-plans-tooling.md`; design spec relocated to `omp-agent-setup/docs/plans/2026-06-23-planning-file-conventions-design.md`).

**Goal:** Make Erenshor conform to the global planning-files convention — one `docs/plans/` tree with front-matter + a generated INDEX, retire the scattered locations, archive shipped work, fix the broken link, delete the dead Typer stub, and wire validation into the commit hook.

**Architecture:** Erenshor *consumes* the global `omp-plans` tool (no local tooling). This plan is a one-time migration of the existing 44 docs + the small per-repo wiring (no-worktrees override, lefthook hook, optional thresholds).

**Tech Stack:** `omp-plans` (global), git, `uv run pytest`, lefthook.

**Scope reference (verified in the 2026-06-23 audit):** `docs/plans/` (28), `docs/superpowers/plans/` (4), `docs/superpowers/specs/` (7), loose `docs/*.md` (5); 9 untracked; 2 undated (`hotrepl-hot-reload-improvements.md`, `nav-target-selection.md`); broken supersede link in `2026-04-18-adventure-guide-nav-stall-consolidation.md`.

---

## Phase A — Consolidate locations

### Task 1: Move superpowers plans/specs into docs/plans/
**Files:** `docs/superpowers/{plans,specs}/*.md` → `docs/plans/`

- [x] **Step 1:** `git mv` (or `mv` for untracked) all 11 files from `docs/superpowers/plans/` and `docs/superpowers/specs/` into `docs/plans/`. Keep filenames (all already `YYYY-MM-DD-…`).
- [x] **Step 1b:** Remove Erenshor's copy of `docs/plans/2026-06-23-planning-file-conventions-design.md` — it is the global feature's spec, relocated to `omp-agent-setup/docs/plans/` (that repo's plan, Task 12). Do **not** migrate, front-matter, or commit it here.
- [x] **Step 2:** `search` the repo for references to the old paths (`docs/superpowers/plans`, `docs/superpowers/specs`) and rewrite them to `docs/plans/`.
- [x] **Step 3:** Remove the now-empty `docs/superpowers/{plans,specs}/` dirs (keep `docs/superpowers/` only if other content remains).
- [x] **Step 4: Commit** — `docs(plans): consolidate superpowers plans/specs into docs/plans`

### Task 2: Place loose docs
**Files:** `docs/PRD-*.md`, `docs/architecture-analysis.md`, `docs/wiki-lua-dev-environment.md`, `docs/vithean-arena-playtest-loot.md`

- [x] **Step 1:** Move the planning artifacts into `docs/plans/` with dated kebab names: `PRD-data-pipeline-rewrite.md` → `docs/plans/<created-date>-prd-data-pipeline-rewrite.md`, `PRD-photo-mode.md` → `…-prd-photo-mode.md` (derive `<created-date>` from first git commit, or file mtime for untracked).
- [x] **Step 2:** Leave genuine **reference** docs in `docs/` (not planning artifacts): `wiki-lua-dev-environment.md`, `architecture-analysis.md`, `vithean-arena-playtest-loot.md`. (If any is really a one-off analysis, classify as `type: audit` and move it instead — decide per file.)
- [x] **Step 3: Commit** — `docs(plans): relocate PRDs into docs/plans; keep reference docs in docs/`

### Task 3: Rename the two undated files
- [x] **Step 1:** `git mv docs/plans/hotrepl-hot-reload-improvements.md docs/plans/<first-commit-date>-hotrepl-hot-reload-improvements.md`; same for `nav-target-selection.md`. Use the first-commit date (`git log --diff-filter=A --format=%cs -- <file> | tail -1`); for untracked, file mtime.
- [x] **Step 2:** Fix any references. **Commit** — `docs(plans): date-prefix the two undated planning docs`

---

## Phase B — Front-matter + verified status

### Task 4: Classify status (verify, don't guess)
**Files:** all `docs/plans/*.md`

- [x] **Step 1:** For each doc, determine `status` from evidence, not the filename: `git log -- <doc>` for activity; check whether the work shipped (code/commits present). Group the obvious clusters: the `2026-03-*`/`2026-04-*` guide + nav + Adventure Guide set is shipped (the mod is released) → `implemented`; one-shot exports (`code-facts-export`, `export-profiling`, `vithean-arena`, `adventure-guide-stable-port`, `repo-history-cleanup`, `playtest-refresh`) → `implemented`; the wiki-cargo umbrella + Phase 3 → `active`; drafts (`website-redesign`, PRDs) → `draft` or `active` per reality.
- [x] **Step 2:** This is parallelizable across read-only agents (one batch, each classifying a slice against git/code, reporting `{slug, status, parent}`); synthesize the results. Do not delete anything on a guess.
- [x] **Step 3:** Record the classification (a scratch list) for Task 5. *(No commit — analysis only.)*
- **Note (completion scope):** `omp-plans status` only counts checkboxes under `## Tasks`/`### Task N`. Legacy plans with other structures report `0/0` or partial ratios — that is expected; rely on `status` for those and **front-matter them without restructuring** their task sections.

### Task 5: Add front-matter to every doc
**Files:** all `docs/plans/*.md`

- [x] **Step 1:** Prepend the YAML front-matter block to each doc: `title` (from the H1), `type` (spec | plan | prd | audit | note — by content), `status` (from Task 4), `created` (first-commit date / mtime), `parent` (umbrella slug where one applies, e.g. the AG cluster → the overhaul program spec; wiki-cargo Phase 3 → the cargo umbrella), `superseded_by`/`archived` where relevant. Preserve existing `## Status` prose only if it adds detail beyond the header; otherwise drop it (status now lives in front-matter).
- [x] **Step 2:** `omp-plans check` → resolve all schema errors (missing/!bad fields).
- [x] **Step 3: Commit** — `docs(plans): add front-matter headers to all planning docs`

---

## Phase C — Archive, fix links

### Task 6: Fix the broken supersede link
**Files:** `docs/plans/2026-04-18-adventure-guide-nav-stall-consolidation.md`

- [x] **Step 1:** Its line 1 points to a nonexistent `…-architecture-consolidation.md`. Set `status: superseded` + `superseded_by: 2026-04-19-adventure-guide-overhaul-program` (the real successor, now in `docs/plans/` after Task 1) in front-matter; fix/remove the broken prose pointer.
- [x] **Step 2:** `omp-plans check` → no `dangling-superseded_by`. **Commit** — `docs(plans): repair the nav-stall supersede link`

### Task 7: Archive shipped/superseded clusters
**Files:** `docs/plans/` → `docs/plans/archive/`

- [x] **Step 1:** `git mv` the `implemented`/`superseded` docs (the 2026-03/04 guide+nav+AG cluster, the one-shot exports, the nav-stall doc) into `docs/plans/archive/`, setting `archived: <today>` in each.
- [x] **Step 2:** `omp-plans check` still green (archived docs are valid link targets). **Commit** — `docs(plans): archive shipped and superseded plans`

### Task 8: Ensure all docs are tracked
- [x] **Step 1:** The 9 untracked docs are now either in `docs/plans/` (active/draft) or `docs/plans/archive/` (dead). `git add` and confirm none remain untracked (`git status` clean for `docs/`).
- [x] **Step 2: Commit** — `docs(plans): track previously-untracked planning docs`

---

## Phase D — Per-repo wiring

### Task 9: Delete the dead `erenshor docs` Typer stub
**Files:** `src/erenshor/cli/main.py:566-591` (+ registration + any test)

- [x] **Step 1:** Remove the `docs` Typer group + its `app.add_typer(...)` registration (clean cutover to `omp-plans`, no alias).
- [x] **Step 2:** `lsp references` / `search` for `docs generate` / the group; remove any CLI help test asserting it.
- [x] **Step 3:** `uv run pytest tests/.../test_cli*.py` → green. **Commit** — `refactor(cli): remove the unimplemented docs command (use omp-plans)`

### Task 10: Per-repo no-worktrees override
**Files:** `AGENTS.md`

- [x] **Step 1:** Add a one-line override (only if not already implied): *"Implement plans inline in the main working tree; do not create git worktrees unless explicitly requested."* Do **not** restate the global planning convention (it's carried by the global AGENTS.md + `skill://planning-files`).
- [x] **Step 2: Commit** — `docs(agent): record the inline/no-worktrees execution preference`

### Task 11: Wire `omp-plans check` into lefthook (+ optional thresholds)
**Files:** `lefthook.yml`; optional `docs/plans/plans.toml`

- [x] **Step 1:** Add a `pre-commit` command that **regenerates the index, re-stages it, then validates**: `omp-plans index` → re-stage `docs/plans/INDEX.md` (lefthook `stage_fixed: true`, or an explicit `git add`) → `omp-plans check`. `check` treats a **stale `INDEX.md` as an error**, so the hook MUST regenerate + re-stage it first — otherwise any plan-doc edit would fail the commit. All steps no-op cleanly when `docs/plans/` is absent.
- [x] **Step 2:** Only if Erenshor wants non-default retention, add `docs/plans/plans.toml` with `stale_days`/`archive_delete_days`; otherwise omit (defaults apply). **No `path` key.**
- [x] **Step 3:** Make a trivial commit touching a doc to confirm the hook runs and passes. **Commit** — `chore(config): validate planning docs in pre-commit`

---

## Phase E — Index + verify

### Task 12: Generate INDEX + final gate
- [x] **Step 1:** `omp-plans index` → write `docs/plans/INDEX.md`; commit it.
- [x] **Step 2:** `omp-plans check` green; `omp-plans status --active` shows the wiki-cargo umbrella + Phase 3 (and nothing stale unexpected). `uv run pytest` green.
- [x] **Step 3: Commit** — `docs(plans): generate INDEX and finalize migration`

---

## Self-review
- **Spec coverage:** consolidate 3 locations (Tasks 1–2), front-matter + verified status (4–5), broken-link fix (6), archive (7), untracked (8), delete stub (9), no-worktrees override (10), lefthook + thresholds (11), INDEX + gate (12). All audit findings addressed.
- **No placeholders:** each task names exact files/commands; classification (Task 4) is verify-not-guess and explicitly parallelizable.
- **Consistency:** `docs/plans/` is the fixed location (no `path` override); cross-repo spec reference is prose, not a `parent` link (parent resolves intra-repo).
- **Safety:** nothing deleted on a guess; archived not deleted; tooling is the global `omp-plans` (this repo adds no tooling).
