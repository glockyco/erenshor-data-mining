---
name: code-facts
description: Hardcoded game constants extracted from the shipped Assembly-CSharp.dll plus structural invariants over re-implemented game logic. Use when the code-facts analyzer fails after a game update, when adding facts or matchers, or when wiring constants derived from game code.
---

# Code Facts

A pinned C# analyzer (`src/tools/CodeFacts/`, ICSharpCode.Decompiler exact-pinned)
decompiles named methods from the shipped `Assembly-CSharp.dll` and runs
declarative fact specs in two modes: **extract** flows hardcoded constants
(drop rates, level gates, upgrade IDs, auction bounds) out as data through the
raw→clean DB pipeline and golden review; **assert** pins structural invariants
that protect Python/Lua code re-implementing game semantics, hard-failing the
refresh when the upstream shape drifts.

## The registry

`src/tools/CodeFacts/specs/erenshor-facts.json` is the single source of
provenance. Every fact lives here; nothing is hand-curated downstream.

- `facts[]` — each spec: `id` (dotted, lowercase), `mode` (`extract`/`assert`),
  `type` (game class), `method`, `matcher`, `args` (matcher-specific),
  optional `variants` (only run this fact for listed variant names), `keys`
  (extract output keys), `note` (why an assert exists + what re-implements it).
- `deferred[]` — facts knowingly **not** modeled, each with the reason (no matcher
  fits, ambiguous binding, non-literal bounds). Read it before adding a spec that
  duplicates a known gap.

Matchers (each binds **exactly once or throws** — no fuzzy fallback):

| Matcher | Semantics |
|---|---|
| `guarded_member_roll` | `rate` + `min_level` from a guarded pool-roll add of `args.member` |
| `string_constants` | the set of `==`-compared string literals in the method |
| `int_comparisons` | integer bounds per member, comma-joined (`args` maps member→key) |
| `statement_shape` | asserts exactly one normalized statement equals `args.statement` |
| `node_shape` | asserts exactly one normalized AST node of `args.kind` equals `args.shape` |
| `string_set` | asserts the `==`-literal set equals `args.strings` exactly |

**Specs pin the DECOMPILER's rendering, not the `.cs` reference files** (e.g.
spaces before `[` / `(`). To get the exact text: run the analyzer and read the
binding error it prints, or decompile with the same pinned decompiler version.

## Commands

`uv run erenshor extract code-facts` runs **between** `extract export` and
`extract build`. It builds the tool, runs it against the shipped DLL, and
replaces the raw `code_facts` / `code_facts_meta` tables. Idempotent — re-running
drops and recreates the tables. `extract build` gates on their presence (step 0);
a missing table means the extract step was skipped, which is an ordering error.

`code_facts_meta` also carries `game_build_id`, the installed Steam build read
from `appmanifest_<app_id>.acf`, and `game_build_published_at`, the nullable
ISO-8601 UTC publication time resolved by exact build-id match against
SteamDB's undocumented build RSS feed. Erenshor publishes only coarse version
strings, so the build ID is the one precise, publicly verifiable identifier for
a game version. It rides here because this command is the last pipeline step
that touches the shipped game files before the clean build, and both values are
carried into the clean DB verbatim, where the maps site reads them for its
data-provenance footer. If the feed is unavailable or the build has aged out
of its window, publication time stores NULL. Consumers omit the provenance
rather than rendering a fabricated local timestamp.

Failure meanings:
- **analyzer exit 1** — a matcher bound ≠ once: the named game method changed shape.
- **build `ValueError` about missing tables** — you ran `build` without `code-facts`.

## Consumer tags

Any Python/Lua constant or rule derived from hardcoded game logic carries a
`# code-fact: <id>` (Python) / `-- code-fact: <id>` (Lua) comment naming its spec.
`tests/test_code_facts_coverage.py` enforces: every tag resolves to a real spec
id, and every **assert** spec has ≥ 1 consumer tag. Tag EVERY re-implementation
site — an untagged assert spec fails the test.

## Failure workflow after a game update

1. `extract code-facts` exits 1 naming one or more fact ids.
2. Open the named method in the freshly-decompiled tree
   (`variants/{v}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp/<Type>.cs`).
3. Re-derive the values/semantics from the new code.
4. Update the spec in `erenshor-facts.json` **and** any tagged consumers together
   (same commit — never split a spec change from its consumers).
5. Re-run `extract code-facts` → `extract build` → `golden capture`.
6. Review the `tests/golden/code_facts/code_facts.csv` diff: extract-value drift
   shows here for sign-off; assert specs only ever read `ok`.

## Discovery layer

A detached git repo at `variants/{v}/decompile-history.git` versions the
decompiled tree across builds. Its git-dir lives **outside** the work tree
because `extract rip` does `rmtree` on the whole Unity project — a `.git`
placed inside `Assembly-CSharp/` would be destroyed on every update. The
`--git-dir`/`--work-tree` flags need no `.git` (or gitlink) inside the wiped
dir, so history survives the rip. `variants/` is gitignored, so the main repo
never sees it. After each re-rip, commit the new tree and diff against the
previous build to catch mechanics no fact spec anticipates:

```bash
G="git --git-dir=variants/{v}/decompile-history.git --work-tree=variants/{v}/unity/ExportedProject/Assets/Scripts/Assembly-CSharp"
$G add -A && $G commit -m "game build <version>"
$G diff HEAD~1 --stat   # churn outside known fact targets = new mechanics
```

`info/exclude` in the bare repo drops `bin/`/`obj/` so build artifacts stay out
of the diff. This is how the `Level > 30` `CrystallizedBalance` / `Planar` world
drops were found. One commit per build; the diff is the discovery tool.

## Policies

- **Shipped DLL only.** Input is `variants/{v}/game/Erenshor_Data/Managed/Assembly-CSharp.dll`.
  The analyzer refuses any path not under `.../Managed/`; NEVER point it at
  `unity/ExportedProject/Library/ScriptAssemblies/` (locally recompiled) or derived files.
- **Decompiler upgrades are standalone commits.** Bumping the ICSharpCode.Decompiler
  pin churns rendering and thus specs — never combine it with a game update.
- **Golden excludes volatile meta.** `code_facts.csv` carries facts only;
  `code_facts_meta` (assembly sha + timestamp) is excluded to avoid capture thrash.

## See also

- `skill://refreshing-game-data` — pipeline order; the re-rip + discovery-commit step
- `skill://unity-export-system` — the asset export the code-facts step runs beside
