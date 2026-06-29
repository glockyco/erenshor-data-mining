---
title: Export Field-Coverage Gate & Playtest Reconciliation
type: spec
status: active
created: 2026-06-29
parent:
---

# Export Field-Coverage Gate & Playtest Reconciliation

A durable gate that fails the export when a game class the exporter reads gains,
loses, or retypes a public field without the change being acknowledged — plus
the one-time reconciliation that seeds it against the current playtest build.

## 1. Purpose & scope

The export code in `src/Assets/Editor/` reads serialized fields off game classes
(`Item`, `Character`, `Spell`, `LootTable`, …). It was largely designed against
an older game build and has only been patched for newer builds **ad hoc** — e.g.
`LootTableProbabilityCalculator.cs` now reads `LootTable.NumberOfGuaranteedDrops`,
a field that exists in the current playtest build but not the older main build.

Two failure modes follow from this:

- **Silent gaps.** A game update adds a field the export *should* capture, and
  nothing notices — the data is simply missing downstream (wiki/map/sheets).
- **Silent misreads.** A field's type or meaning changes and the export keeps
  reading it, now wrong.

The compiler catches exactly one sub-case — a *removed* field a listener
*statically references* — as a hard `CS1061`. It catches neither added fields
nor type changes nor removals of fields read indirectly. This spec closes the
structural half of that gap with a checked-in **field-coverage manifest** and a
**pre-export gate** that enforces it, and uses the same manifest's one-time
seeding to reconcile the export against the current playtest build.

**Why now:** Phase 3 of the wiki-cargo work (and every future game update)
builds on the export's output. A complete, correct export is the foundation;
the gate keeps it complete as playtest takes further updates before it merges to
main, without manual re-checking each time.

**In scope:** structural drift (added / removed / retyped *public* fields) on the
game types the export reads; the one-time reconciliation that seeds the manifest
and fixes the gaps it surfaces.

**Out of scope (non-goals):**

- **Private `[SerializeField]` fields.** Public fields only — the gate's surface
  matches what the export actually reads, so it never gates fields the export
  structurally cannot consume.
- **Semantic drift** (a field's *meaning* changes, signature unchanged) — that is
  code-facts `assert`'s job (§3).
- **Value correctness** (the export emits the *right* data) — golden + unit tests.
- **Verifying the `captured` annotation is truthful** — that stays human
  discipline, the same trust model `PublicApiAnalyzers` uses (§5).
- **Supporting multiple game versions simultaneously.** At any time exactly one
  game version is in focus; the manifest tracks that one version (§7).

## 2. Background (verified)

- The export compiles and runs on **playtest** (build 23947734, gate green) but
  **fails to compile on main** — `LootTable.NumberOfGuaranteedDrops` does not
  exist in main's older build (`CS1061` at `LootTableProbabilityCalculator.cs`
  lines 100, 314). Main's last successful export was build 22374607 (pre-dynamic-
  spawn). Non-playtest exports are therefore already broken by the playtest-
  coupled export code.
- `DynamicSpawnSourceListener` already reflects over game types at export time;
  the dynamic-spawn gate already emits a structured envelope and `EditorApplication.Exit(3)`.
- `src/tools/CodeFacts/` is a pinned C# analyzer that already inspects the
  shipped `Assembly-CSharp.dll` (`.../Managed/Assembly-CSharp.dll` only) and is
  driven by `uv run erenshor extract code-facts`.

## 3. Architecture — three layers, one job each

| Layer | Catches | Mechanism | Status |
|---|---|---|---|
| **Field-coverage gate** | **Structural** drift — public field added / removed / retyped on an export-touched game type | metadata read of the shipped DLL vs a checked-in manifest, pre-export | **new (this spec)** |
| **code-facts `assert`** | **Semantic** drift — re-implemented game *logic* changes shape | `extract code-facts` analyzer | exists |
| **golden + unit tests** | **Value** correctness — the export emits the right data | clean-build pipeline | exists |

The layers do not overlap. Only the field-coverage gate is new.

## 4. The manifest

A single checked-in JSON file describing the **public instance field surface of
every export-touched game type** for the game version currently in focus. JSON
keeps it in the code-facts data-format family (`erenshor-facts.json`) and parses
off-the-shelf in both the C# tool and Python tests — no custom grammar and no
escaping traps (an `ignored` reason may contain any characters). Reads are a
plain `JsonSerializer`. The file stays sorted by key with one field entry per
line — kept so by a formatting-only normalize pass that never touches
classifications — so diffs stay granular and reviewable:

```json
{
  "tracks_build": "23947734",
  "types": ["Character", "Item", "LootTable", "Spell"],
  "fields": {
    "Character": {
      "SpawnOnDeath": { "type": "UnityEngine.GameObject", "status": "captured", "by": "DynamicSpawnSourceListener" }
    },
    "Item": {
      "InspectorIconOverride": { "type": "UnityEngine.Sprite", "status": "ignored", "reason": "editor-only, not data" },
      "RareItem":              { "type": "System.Boolean", "status": "captured", "by": "ItemListener" }
    },
    "LootTable": {
      "NumberOfGuaranteedDrops": { "type": "System.Int32", "status": "captured", "by": "LootTableProbabilityCalculator" }
    }
  }
}
```

- `fields` — two-level: **fully-qualified CLR type name** (Mono.Cecil `FullName` —
  bare for Erenshor's global-namespace game types, `Namespace.Type` / `Outer/Inner`
  otherwise) → field name → entry. Two levels rather than a `Type.Field`
  concatenation, so namespaced/nested types stay unambiguous; sorted at both
  levels. Each entry carries its field `type` (also FQ, so a **retype** is a diff
  and is caught) and exactly one `status`:
  - `"captured"` + `"by": "<listener>"` — flows into the export; the listener
    name is human documentation of intent, **not** machine-verified.
  - `"ignored"` + `"reason": "<why>"` — deliberately not exported.
- `types` — the explicit in-scope set (fully-qualified names), so invariant 3 (§5) is a plain set check.
- `tracks_build` — provenance only; **no gate logic branches on it**.

The checker is **read-only on classifications** — it never writes
`status`/`by`/`reason`. An in-scope field absent from the manifest, a stale
entry, or a retype is reported in the **failure envelope** (with a paste-ready
snippet to classify), never committed automatically — so the manifest only ever
holds human-classified entries (the no-bulk-accept rule). **Location:**
`src/tools/ExportSurface/field-coverage.json` — version-controlled beside its tool. **One file** — it describes the
one focused version; there are no per-variant manifests.

## 5. The gate — three machine invariants, zero body parsing

The checker reads the shipped DLL's metadata and enforces:

1. **Completeness** — every public instance field of each in-scope type is
   classified in the manifest. An unclassified field → fail.
2. **No staleness / retype** — every manifest line maps to a field that still
   exists with the same type. A vanished or retyped field → fail.
3. **Listener-type coverage** — every `IAssetScanListener<T>` *declaration*
   (regex over listener declarations, never method bodies) has its `T` present as
   an in-scope type. Catches "added a listener, forgot the manifest."

The gate never parses listener bodies and never executes game code, so it makes
no claim about whether a `captured` field is genuinely read — only that the field
surface is fully accounted for and nothing is stale. This is the
`PublicApiAnalyzers` trust model: the baseline is hand-maintained; the analyzer
checks membership, not semantics.

**Anti-friction (the dominant failure mode of such gates):** there is **no bulk
"accept all"**. Each finding is cleared by a human writing one classification
line, the manifest stays granular and sorted so a game update yields a small
readable diff, and the classification carries intent (`captured`/`ignored` +
reason). These are the defenses the snapshot/approval-testing literature
identifies against gates decaying into rubber stamps.

**Scope boundary — in-scope types:** the manifest's declared type set, seeded
from listener `<T>` generic arguments plus hand-added nested types a listener
reads (e.g. `LootTable`). The gate is **type-based, not data-dependent** — it
inspects `Item`'s declared fields regardless of which assets a scene contains.

## 6. Tooling & pipeline wiring

**Tool.** A **sibling project** `src/tools/ExportSurface/` — *not* a CodeFacts
mode. CodeFacts is a post-export data producer that pins the decompiler fragilely
on purpose; this is a pre-export gate that wants a boring, stable metadata reader,
so they stay decoupled — separate dependencies, separate pipeline positions. It
mirrors CodeFacts' shape (thin CLI, `.../Managed/Assembly-CSharp.dll`-only policy,
JSON output) and runs through the Typer CLI, but shares no code or version pin
with it. It owns invariants 1–2 (DLL metadata ↔ manifest); invariant 3 lives in
the precondition layer (see *When it runs*).

**Metadata-only reading.** Field signatures come from DLL **metadata** via
`Mono.Cecil` (the standard standalone metadata reader) — **never** runtime `Assembly.LoadFrom` +
reflection. The checker therefore never resolves Assembly-CSharp's dependency
closure (UnityEngine, third-party) and never needs Unity. This is what makes it
genuinely **pre-compile** and able to run before `extract export`.

**When it runs.** As a **precondition of `extract export`** (the CLI precondition
system in `src/erenshor/cli/preconditions/` already exists), so it fires
automatically on every export — no manual step — and *before* Unity compiles, so
a statically-referenced removal surfaces as the friendly envelope instead of a
raw `CS1061`. The precondition orchestrates the verdict — it invokes the C#
sibling for invariants 1–2 and itself runs the invariant-3 declaration-regex over
`src/Assets/Editor/.../Listener/*.cs`, merging both into one pass/fail + a
structured envelope mirroring the dynamic-spawn gate's.

**Canonical order:** `rip → [field-coverage check] → export → code-facts → build`.

## 7. Single-target version model

At any time exactly one game version is in focus (currently playtest). The one
manifest describes that version's surface; the gate is **always strict** and
behaves **identically regardless of which variant is loaded** — there is no
baseline/lagging distinction, no variant-aware branching, no fallback paths.

Running the export against a version that does not match the manifest reports
drift, which is accurate (that version differs from the manifest's version) and
is not a case we add special handling for — non-focused-version exports are
simply not a supported activity. When focus shifts (playtest → main at the
merge), the manifest is **re-seeded** for the new build; that re-seed is the
normal post-game-update step (`skill://refreshing-game-data`), not a mode.

## 8. Reconciliation — the one-time port

Seeding the manifest is the actual "port the export to playtest" work:

1. **Derive in-scope types** — listener `<T>` declarations + hand-added nested
   types.
2. **Enumerate** the current playtest DLL's public instance fields per in-scope
   type (the tool, metadata-only).
3. **Classify every field once** — `captured(<listener>)` or `ignored(<reason>)`.
   This first pass is comprehensive (the accepted upfront cost).
4. **The leftovers are the audit findings:**
   - fields present but unread that look data-relevant → candidate **new captures**
     (export changes — new/extended listeners + records + clean-DB columns);
   - fields whose type differs from what the export assumes → **silent-misread**
     review.
5. **Resolve** — implement the wanted captures, or mark the rest `ignored` with a
   reason.
6. **Commit** the manifest as the current-version baseline; the gate is now live.

## 9. Testing & verification

- **Tool unit tests:** against fixture types + a fixture manifest, assert each
  invariant detects added / removed / retyped / unclassified correctly; assert
  deterministic ordering and envelope shape.
- **Negative test:** a deliberately-stale manifest entry fails; a deliberately-
  unclassified field fails.
- **Integration:** the gate passes on the reconciled playtest manifest; injecting
  a synthetic field into a fixture fails it.
- **The manifest is reviewed as code** in every PR that changes it — the human
  layer the design depends on.
- Existing golden + unit suites continue to assert value correctness; code-facts
  asserts continue to assert semantics.

## 10. Key decisions

- One manifest, one strict gate, one target = the single game version in focus;
  re-seed on a version switch; no variant branching or fallbacks.
- Public fields only; the gate surface equals the export's read surface.
- Metadata-only DLL reading (Mono.Cecil), never runtime
  reflection — keeps the gate pre-compile and Unity-independent.
- Pre-export CLI precondition, so it is automatic and beats the compiler to
  referenced removals.
- Two classifications (`captured`/`ignored`); spawn fields are
  `captured(DynamicSpawnSourceListener)` — no third verb, no cross-gate
  bookkeeping; the field-coverage and dynamic-spawn gates are siblings on
  mostly-different surfaces.
- Structural (this gate) / semantic (code-facts) / value (golden) layers stay
  separate.
- No bulk-accept; granular sorted manifest with intent annotations — the
  anti-rubber-stamp defenses.
- Tool is a sibling project (`src/tools/ExportSurface/`), not a CodeFacts mode —
  decoupled lifecycle (pre-export gate vs post-export producer) and dependency
  (its own Mono.Cecil reader, not CodeFacts' fragile decompiler pin).
- One tracked manifest at `src/tools/ExportSurface/field-coverage.json`.
- Invariant 3 ships as core, in the Python `extract export` precondition (needs
  editor source, not the DLL); the C# sibling owns invariants 1–2.

## 11. References

- Roslyn `PublicApiAnalyzers` (`PublicAPI.Shipped.txt` / `Unshipped.txt`) — the
  checked-in surface baseline + fail-on-diff pattern this gate adapts:
  https://github.com/dotnet/roslyn/blob/main/src/RoslynAnalyzers/PublicApiAnalyzers/PublicApiAnalyzers.Help.md
- .NET API baselines in practice (aspnetcore):
  https://github.com/dotnet/aspnetcore/blob/main/docs/APIBaselines.md
- Snapshot/approval-testing pitfalls (re-approval friction, large unreviewable
  diffs, determinism) — the anti-friction rationale: Kent C. Dodds, "Effective
  Snapshot Testing" https://kentcdodds.com/blog/effective-snapshot-testing
- `skill://unity-export-system`, `skill://code-facts`, `skill://refreshing-game-data`.
