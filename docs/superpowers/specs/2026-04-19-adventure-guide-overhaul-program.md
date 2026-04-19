# AdventureGuide Overhaul — Program Spec

**Date:** 2026-04-19
**Status:** Approved in chat
**Scope:** Meta-document organizing how the AdventureGuide architecture overhaul proceeds. Addresses all 11 themes from `docs/plans/2026-04-18-ag-architecture-audit.md`, the TimeOfDay correctness bug, and the extractable incremental engine that arises from the reactive-core work.

---

## 1. Why this document exists

The audit identified 11 architectural themes, 1 correctness bug, and 1 rendering spike opportunity. Designing all of these in a single session would produce shallow decisions at each point. Designing them entirely separately would re-decide shared concepts (facts, revisions, phase ordering, type shapes) repeatedly. This document decomposes the work into coupled design groups, orders them by dependency, and records the meta-decisions (scope, ordering, extraction strategy) so each per-group brainstorming session can focus on real architectural calls.

The program spec **does not** make per-group design decisions. Those happen in each group's own brainstorming session.

## 2. Scope

**In scope:**
- All 11 audit themes (T1–T11)
- TimeOfDay fact correctness bug (`src/mods/AdventureGuide/src/State/LiveStateTracker.cs:206-209, 950-952`)
- Extraction-friendly namespace design for the incremental engine that emerges from Group 1

**Deferred to after program completion:**
- **T9** ImGui/ILRepack spike — afternoon research task; outcome eliminates ~700 LOC of rendering code or confirms the workaround is structural
- Engine extraction to standalone repo — evaluated only after all 4 groups + cleanup stream complete; explicitly nice-to-have, abandonable without regret if the API did not generalize cleanly

**Out of scope forever (for this program):**
- Speculative roadmap features. The audit addresses what exists today; so does this program.

## 3. Decomposition

### Group 1 — Reactive core

- **Audit themes:** T2 (facts-system adoption, scene-independent caching, `MarkerComputer` as derived view), T3 (cache-invalidation unification — subsumed by T2's "adopt fact-deltas everywhere" prescription), T4 (`UpdateOrchestrator` extraction)
- **Additional artifact:** extraction-friendly incremental engine. Own namespace (e.g. `AdventureGuide.Incremental`), no Erenshor-specific types in the public API, isolated tests.
- **Audit questions to resolve in the Group 1 brainstorming session:**
  - Q1 — `QuestResolutionRecord` phase/item snapshots: canonical or redundant?
  - Q5 — `MaintainedViewPlanner` role in a fact-driven world

### Group 2 — Type shapes

- **Audit themes:** T1 (`Node` and `MarkerEntry` discriminated unions), T5 (`InteractionLabelFormatter` consolidating 4 text builders)
- **Audit questions to resolve in the Group 2 brainstorming session:**
  - Q2 — which of 26 `NodeType` variants are produced by the Python pipeline today vs. aspirational?
  - Q3 — `EdgeType` × `NodeType` taxonomy formalization
  - Q6 — confirmation of no planned Door/ZoneLine marker kinds (tightens `MarkerEntry` discriminated-union design)

### Group 3 — Navigation coherence

- **Audit theme:** T7 (`NavigationTargetSelector` vs. `NavigationTargetResolver` split-brain)
- No audit questions outstanding

### Group 4 — Diagnostics decoupling

- **Audit theme:** T8 (`DiagnosticsCore` threaded through every subsystem, `DebugAPI` static-global registry)
- **Dependency:** builds on Group 1's `UpdateOrchestrator` as the seam for recording spans at phase boundaries rather than inside each subsystem
- No audit questions outstanding

### Cleanup stream (opportunistic, no spec, one commit per item)

Interleaves between groups wherever convenient.

- TimeOfDay bug fix (1 line; ship anytime, recommended early)
- T6 dead-code deletions: `CreatePendingCompletionEntry`, `GetNodeType(int)`, `zone_line_ids` field, discarded `positionResolvers` ctor param, unused `ResolveTargets`/`ResolveUnlockTargets`, 8 `State/Resolvers/*.cs` thin wrappers, `LiveStateBackedPositionResolver` base, `CharacterMarkerPolicy`, `ItemSourceVisibilityPolicy`, `NavigationDisplay`
- T6 file moves: `State/NavigationHistory.cs`, `State/NavigationSetPersistence.cs`, `State/GameUIVisibility.cs`, `State/GameWindowOverlap.cs` out of `State/`
- T10 fixes: `TrackerPanel` animation ownership → `TrackerState`; `FilterState.LoadFrom` two-phase init → factory; `SpecTreeProjector` cache key → typed record
- T11 fixes: `ResolutionSession` public-mutable-collections encapsulation; `FrontierEntry.RequiredForQuestIndex` `-1` sentinel → `int?`; `SourceResolver.ResolveEntry` routing-strategy doc comment; `EffectiveFrontier.Phases` live-vs-snapshot doc

## 4. Dependencies and ordering

```
TimeOfDay bug (standalone, anytime)

Group 1 ───► Group 2 ───► Group 3 ───► Group 4
   │                                      ▲
   └──────────────────────────────────────┘
   (Group 4 depends on Group 1's UpdateOrchestrator)

Cleanup stream interleaves between groups
T9 spike + extraction evaluation after Group 4 completes
```

**Order:** 1 → 2 → 3 → 4.

- **G1 first.** Load-bearing; G4 depends on it.
- **G2 second.** Highest ongoing-feature leverage. Doing G2 after G1 means derived-view pattern matching is rewritten **once** (against the new discriminated-union type); doing G2 before G1 would force it to be rewritten twice (once for types, once for fact-driven invalidation). The audit explicitly flagged T1 as "the single biggest source of compounding friction."
- **G3 third.** Standalone, independent of all other groups.
- **G4 last.** Natural follow-up to G1's orchestrator seam; lowest urgency.

## 5. Per-group lifecycle

Each group follows the same lifecycle:

1. **Brainstorming session** (this skill) → design spec at `docs/superpowers/specs/2026-MM-DD-ag-<group>-design.md`, committed
2. **Implementation plan** via `writing-plans` skill → plan doc at `docs/superpowers/plans/2026-MM-DD-ag-<group>.md`, committed
3. **Implementation** in incremental commits on the current branch or a sub-branch
4. **Per-commit gates:**
   - 283+ tests green (`dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build`)
   - Mod builds clean (`uv run erenshor mod build --mod adventure-guide`)
   - F6 hot-reload deploys cleanly in a running game
   - Incident dump shows no new `FrameStall`/`FrameHitch` under representative scene load
   - Golden diffs reviewed if any data-path changes
5. **Group exit:** all themes within the group's scope are materially resolved against the audit report. The audit serves as the completion checklist — each theme's "what it blocks" / "evidence of pain" narrative should no longer hold.

## 6. Engine extraction (post-completion, nice-to-have)

After all 4 groups + cleanup stream complete:

- Evaluate whether the `AdventureGuide.Incremental` namespace generalized cleanly during adoption by Groups 2, 3, and 4.
- If it did: extract to a standalone repository (tentatively `IncC#` or similar), port tests, write a README that honestly positions it against Salsa (Rust), Incremental.NET (F#), and UniMob (Unity-coupled), and publish.
- If it did not: leave it in-mod. No regret. No forcing.

Extraction is explicitly **not a goal of the program** — it is a potential downstream benefit. Group 1's design should make extraction *possible* by keeping the engine in its own namespace with no Erenshor types in the public API, but it should not compromise Erenshor-specific ergonomics for hypothetical external consumers.

## 7. Success criteria for the program

- All 11 audit themes addressed; each theme's "what it blocks" concerns materially resolved
- TimeOfDay bug fixed
- Test count ≥ current baseline (283); any additions welcome, no net loss
- No new `FrameStall` or `FrameHitch` incidents under representative scene load (Stowaway, 5 active + 5 completed quests, selected quest with resolution summary)
- `AdventureGuide.Incremental` namespace exists with zero Erenshor type references in its public API surface
- Final extraction decision recorded (extract / abandon) with one-paragraph rationale

## 8. What happens next

Immediately after this program spec is approved and committed:

1. Ship the TimeOfDay bug fix as a standalone commit (1-line, independent of everything else).
2. Begin Group 1 brainstorming session. Its spec will live at `docs/superpowers/specs/2026-MM-DD-ag-reactive-core-design.md`.

After Group 1 ships, the Group 2 brainstorming session begins, and so on through Group 4. T9 spike and engine extraction evaluation are the last two items, run in either order after Group 4 completes.
