---
name: code-facts
description: Resolve code-facts extraction failures after a game update or add a fact that must track a shipped game method.
---

# Code facts

Run `uv run erenshor -V {v} extract code-facts` after export and before the clean build. The analyzer reads the installed game's `Erenshor_Data/Managed/Assembly-CSharp.dll`, not a locally compiled Unity assembly. It writes `code_facts` and `code_facts_meta` into the raw database. The clean build rejects missing or empty metadata.

## When extraction fails

1. Read the failing fact IDs and binding errors. Open their methods in the freshly ripped `Assembly-CSharp` scripts. Compare the method with the preceding build's backed-up scripts.
2. Re-derive each affected value or rule from the new shipped code. Check both the spec and every consumer that implements that rule. Do not change a spec only to silence a binding error.
3. Edit `src/tools/CodeFacts/specs/erenshor-facts.json`. Use `extract` for values that enter the clean database and `assert` for structural rules implemented by consumers. Use `variants` only when the fact is variant-specific.
4. If a matcher binds zero or multiple nodes, inspect the analyzer's error and the pinned decompiler rendering. `statement_shape` and `node_shape` compare normalized decompiled syntax, not text copied from the ripped `.cs` files. Add a narrowly scoped matcher when none can bind the real rule.
5. Update affected Python, Lua, or C# export consumers and their `# code-fact: <id>`, `-- code-fact: <id>`, or `// code-fact: <id>` tags. Run `uv run erenshor -V {v} extract code-facts` again, then `uv run erenshor -V {v} extract build`.
6. Review the `code_facts` rows in the report of `uv run erenshor -V {v} extract changes`. An `assert` fact emits `ok`, and extracted values appear by key.

The registry also lists deferred facts. Check it before adding a spec. `tests/contract/tools/test_code_facts_coverage.py` checks tags in `src/erenshor/`, `wiki/modules/`, and the C# export under `src/Assets/Editor/`: each tag must name a spec, and each `assert` spec needs a tagged consumer there.

## When behaviour coverage fails

The run lists each script type whose code reads or writes one of the progression-state APIs declared in `src/tools/CodeFacts/BehaviourCoverage.cs`, and checks each against `src/tools/CodeFacts/specs/behaviour-coverage.json`. It fails on an unlisted type, a stale entry, a changed set of APIs, and a `pending` entry without a task.

1. Open the named type in the freshly ripped scripts and compare it with the preceding build's backed-up scripts.
2. Find what models its effect. The README's Progression concept names the mechanisms that the clean build models, and the processor modules in `src/erenshor/application/processor/` implement them. An export listener or processor rule makes it `adapter`, and a core pipeline component makes it `core`, each with that component named. A controller that no rule models yet gets one through the procedure in `skill://unity-export-system`. Make it `excluded` only when its code shows that it cannot gate progression, and put that code evidence into the reason. Otherwise make it `pending` with the task of an open OpenSpec change that will model it. Never exclude a type because its feature is out of a change's scope.
3. Record the entry with its exact set of APIs, then rerun `uv run erenshor -V {v} extract code-facts`.
4. When a review finds a gate that the inventory missed, add the API that reveals it to the declared list in `BehaviourCoverage.cs` in the same commit, and classify the types that it adds.

## Failure recovery

- If `extract build` reports missing code-facts tables, rerun `extract code-facts` after the latest export. Export replaces the raw database.
- If code-facts extraction cannot read the Steam build ID, inspect the installed Steam app manifest. If the SteamDB feed cannot be fetched or parsed, restore access and retry. An old build absent from the feed can have a null publication time.
- If the analyzer refuses a DLL path, use the shipped copy under `Erenshor_Data/Managed/`. Never substitute Unity's `Library/ScriptAssemblies` output.
- Review decompiler dependency upgrades separately from game updates. A new decompiler rendering can change syntax-bound specs without changing game logic.

Follow `skill://refreshing-game-data` for the full update order.
