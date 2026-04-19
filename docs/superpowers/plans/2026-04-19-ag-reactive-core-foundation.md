# AdventureGuide Reactive Core Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use skill://superpowers:subagent-driven-development (recommended) or skill://superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the incremental engine, the `GuideReader` wrapper, and the four resolution queries that replace `QuestResolutionService` + `GuideDependencyEngine`, ending with the engine wired into `Plugin.Update` and all quest-resolution consumers reading through it.

**Architecture:** Salsa-shaped query engine (memoised `(query, key)` entries, revision-based invalidation, value-equality backdating, lazy recomputation) in its own namespace `AdventureGuide.Incremental`. An Erenshor-specific wrapper `GuideReader` binds the engine's fact-key generic to the mod's `FactKey`. Queries are registered at startup and read by consumers through `GuideReader`.

**Spec:** `docs/superpowers/specs/2026-04-19-ag-reactive-core-design.md`.

**Follow-up plan (separate):** `MarkerCandidates` query design, `MarkerComputer` → `MarkerProjector` surgery, `MaintainedViewPlanner` deletion, `NavigationTargetSelector` simplification, and the five-phase orchestrator extraction. Blocked by Plan A completion because these all ride on the engine this plan installs.

**Tech Stack:** C# 10, .NET Framework 4.7.2 (BepInEx), xUnit, Unity 2021.3.45f2.

---

## Scope Contract

**In scope for this plan:**
- `AdventureGuide.Incremental` namespace (engine, query handle, read context, query reference)
- `GuideReader` wrapper in `AdventureGuide.State`
- `FactKey`/`FactKind`/`ChangeSet` renames (drops unjustified `Guide*` prefix)
- Four queries: `CompiledTargets(questKey)`, `BlockingZones(scene)`, `NavigableQuests()`, `QuestResolution(questKey, scene)`
- `QuestResolutionRecord` drops phase/item-count snapshots
- Plugin wires engine; scene change is a fact, not a special path
- Deletes: `QuestResolutionService`, `GuideDependencyEngine`, `GuideDerivedKey`, `GuideDerivedKind`

**Out of scope (Plan B):**
- `MarkerCandidates` query
- `MarkerComputer` → `MarkerProjector` rename and surgery
- `MaintainedViewPlanner`/`MaintainedViewPlan` deletion (still present, still called)
- `NavigationTargetSelector` simplification
- Five-phase orchestrator extraction from `Plugin.Update`
- Version counters and dirty flags on subsystems not touched here

**Per-task acceptance gate:** test suite stays green (`dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo`), mod builds clean, each commit is atomic.

---

## File Structure

**New files:**
- `src/mods/AdventureGuide/src/Incremental/Engine.cs` — `Engine<TFactKey>` with memoisation, revision tracking, lazy recomputation, backdating, cycle detection
- `src/mods/AdventureGuide/src/Incremental/Query.cs` — `Query<TKey, TValue>` handle
- `src/mods/AdventureGuide/src/Incremental/ReadContext.cs` — `ReadContext<TFactKey>` exposing `RecordFact` and transparent query-to-query `Read`
- `src/mods/AdventureGuide/src/Incremental/QueryRef.cs` — untyped query handle used in the invalidation-result set
- `src/mods/AdventureGuide/src/State/GuideReader.cs` — Erenshor wrapper over `ReadContext<FactKey>`
- `src/mods/AdventureGuide/src/Resolution/Queries/CompiledTargetsQuery.cs`
- `src/mods/AdventureGuide/src/Resolution/Queries/BlockingZonesQuery.cs`
- `src/mods/AdventureGuide/src/Resolution/Queries/QuestResolutionQuery.cs`
- `src/mods/AdventureGuide/src/Navigation/Queries/NavigableQuestsQuery.cs`
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Incremental/EngineTests.cs`
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Incremental/ReadContextTests.cs`
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/State/GuideReaderTests.cs`
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Resolution/QueriesTests.cs` (covers all four queries)

**Mechanically renamed (Task 2):**
- `src/mods/AdventureGuide/src/State/GuideFactKey.cs` → keeps filename; types inside become `FactKey`/`FactKind` (file rename happens naturally via git mv)
- `src/mods/AdventureGuide/src/State/GuideChangeSet.cs` → `ChangeSet.cs`

**Modified (Task 5 cutover):**
- `src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs` — drops snapshot fields, becomes a `record`
- `src/mods/AdventureGuide/src/Plugin.cs` — wires engine; deletes the dependency-engine invalidation branch; scene change flows through facts
- All consumers of `QuestResolutionService.ResolveQuest`/`ResolveBatch` — switch to `guideReader.ReadQuestResolution`

**Deleted (Task 5):**
- `src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs`
- `src/mods/AdventureGuide/src/State/GuideDependencyEngine.cs`
- `src/mods/AdventureGuide/src/State/GuideDerivedKey.cs`
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/QuestResolutionServiceTests.cs` (content migrates to new tests where behaviour is still relevant)
- `src/mods/AdventureGuide/tests/AdventureGuide.Tests/QuestResolutionInvalidationTests.cs` (same)

---

### Task 1: Engine infrastructure (`AdventureGuide.Incremental`)

**Goal:** Self-contained Salsa-shaped engine with zero Erenshor dependencies. TDD: write engine semantics tests first, then implement.

**Files:**
- Create: `src/mods/AdventureGuide/src/Incremental/Engine.cs`
- Create: `src/mods/AdventureGuide/src/Incremental/Query.cs`
- Create: `src/mods/AdventureGuide/src/Incremental/ReadContext.cs`
- Create: `src/mods/AdventureGuide/src/Incremental/QueryRef.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Incremental/EngineTests.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Incremental/ReadContextTests.cs`

- [ ] **Step 1.1: Write the engine semantics test file**

Create `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Incremental/EngineTests.cs`:

```csharp
using AdventureGuide.Incremental;
using Xunit;

namespace AdventureGuide.Tests.Incremental;

public sealed class EngineTests
{
	private readonly record struct TestFact(string Name);

	[Fact]
	public void Read_ComputesOnce_WhenNoInvalidationOccurs()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var query = engine.DefineQuery<string, int>(
			name: "Double",
			compute: (ctx, key) => { computeCount++; return key.Length * 2; });

		int first = engine.Read(query, "hello");
		int second = engine.Read(query, "hello");

		Assert.Equal(10, first);
		Assert.Equal(10, second);
		Assert.Equal(1, computeCount);
	}

	[Fact]
	public void Read_Recomputes_AfterFactInvalidation()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var fact = new TestFact("counter");
		var query = engine.DefineQuery<int, int>(
			name: "ReadFact",
			compute: (ctx, key) => { ctx.RecordFact(fact); computeCount++; return key; });

		engine.Read(query, 7);
		engine.InvalidateFacts(new[] { fact });
		engine.Read(query, 7);

		Assert.Equal(2, computeCount);
	}

	[Fact]
	public void InvalidateFacts_IsLazy_NoComputeBeforeRead()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var fact = new TestFact("x");
		var query = engine.DefineQuery<int, int>(
			name: "Lazy",
			compute: (ctx, key) => { ctx.RecordFact(fact); computeCount++; return key; });

		engine.Read(query, 1);
		Assert.Equal(1, computeCount);

		engine.InvalidateFacts(new[] { fact });
		engine.InvalidateFacts(new[] { fact });
		engine.InvalidateFacts(new[] { fact });

		Assert.Equal(1, computeCount);
	}

	[Fact]
	public void Read_SkipsRecompute_WhenUnrelatedFactInvalidated()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var factA = new TestFact("a");
		var factB = new TestFact("b");
		var query = engine.DefineQuery<int, int>(
			name: "OnlyA",
			compute: (ctx, key) => { ctx.RecordFact(factA); computeCount++; return key; });

		engine.Read(query, 1);
		engine.InvalidateFacts(new[] { factB });
		engine.Read(query, 1);

		Assert.Equal(1, computeCount);
	}

	[Fact]
	public void Backdating_SuppressesRippleWhenValueUnchanged()
	{
		var engine = new Engine<TestFact>();
		int dependentComputes = 0;
		var fact = new TestFact("source");
		int sourceValue = 42;

		var source = engine.DefineQuery<int, int>(
			name: "Source",
			compute: (ctx, key) => { ctx.RecordFact(fact); return sourceValue; });
		var dependent = engine.DefineQuery<int, int>(
			name: "Dependent",
			compute: (ctx, key) => { dependentComputes++; return ctx.Read(source, key) + 1; });

		engine.Read(dependent, 0);
		Assert.Equal(1, dependentComputes);

		engine.InvalidateFacts(new[] { fact });
		engine.Read(dependent, 0);

		Assert.Equal(1, dependentComputes);
	}

	[Fact]
	public void Backdating_RipplesWhenValueChanges()
	{
		var engine = new Engine<TestFact>();
		int dependentComputes = 0;
		var fact = new TestFact("source");
		int sourceValue = 42;

		var source = engine.DefineQuery<int, int>(
			name: "Source",
			compute: (ctx, key) => { ctx.RecordFact(fact); return sourceValue; });
		var dependent = engine.DefineQuery<int, int>(
			name: "Dependent",
			compute: (ctx, key) => { dependentComputes++; return ctx.Read(source, key) + 1; });

		engine.Read(dependent, 0);
		sourceValue = 99;
		engine.InvalidateFacts(new[] { fact });
		engine.Read(dependent, 0);

		Assert.Equal(2, dependentComputes);
	}

	[Fact]
	public void QueryToQueryDependency_IsRecordedTransparently()
	{
		var engine = new Engine<TestFact>();
		var fact = new TestFact("leaf");
		int leafValue = 5;

		var leaf = engine.DefineQuery<int, int>(
			name: "Leaf",
			compute: (ctx, key) => { ctx.RecordFact(fact); return leafValue; });
		var parent = engine.DefineQuery<int, int>(
			name: "Parent",
			compute: (ctx, key) => ctx.Read(leaf, key) * 10);

		Assert.Equal(50, engine.Read(parent, 0));

		leafValue = 7;
		engine.InvalidateFacts(new[] { fact });

		Assert.Equal(70, engine.Read(parent, 0));
	}

	[Fact]
	public void CycleInQueryGraph_Throws()
	{
		var engine = new Engine<TestFact>();
		Query<int, int>? b = null;
		var a = engine.DefineQuery<int, int>(
			name: "A",
			compute: (ctx, key) => ctx.Read(b!, key) + 1);
		b = engine.DefineQuery<int, int>(
			name: "B",
			compute: (ctx, key) => ctx.Read(a, key) + 1);

		Assert.Throws<InvalidOperationException>(() => engine.Read(a, 0));
	}

	[Fact]
	public void InvalidateFacts_ReturnsAffectedQuerySet()
	{
		var engine = new Engine<TestFact>();
		var fact = new TestFact("shared");
		var q1 = engine.DefineQuery<int, int>(
			name: "Q1",
			compute: (ctx, key) => { ctx.RecordFact(fact); return key; });
		var q2 = engine.DefineQuery<int, int>(
			name: "Q2",
			compute: (ctx, key) => { ctx.RecordFact(fact); return key + 1; });

		engine.Read(q1, 0);
		engine.Read(q2, 0);

		var affected = engine.InvalidateFacts(new[] { fact });

		Assert.Equal(2, affected.Count);
	}
}
```

- [ ] **Step 1.2: Run tests to verify they all fail (compile errors)**

```bash
dotnet build src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj -v quiet -nologo
```

Expected: compile errors referencing missing `Engine`, `Query`, `ReadContext` types.

- [ ] **Step 1.3: Implement `QueryRef.cs`**

Create `src/mods/AdventureGuide/src/Incremental/QueryRef.cs`:

```csharp
namespace AdventureGuide.Incremental;

/// <summary>Untyped handle identifying a specific <c>(query, key)</c> cache entry.
/// Returned by the engine's invalidation methods so callers can observe which
/// entries were marked stale without leaking the engine's internal cache type.</summary>
public readonly struct QueryRef : IEquatable<QueryRef>
{
	internal QueryRef(string queryName, object key)
	{
		QueryName = queryName;
		Key = key;
	}

	public string QueryName { get; }
	public object Key { get; }

	public bool Equals(QueryRef other) =>
		QueryName == other.QueryName && Equals(Key, other.Key);

	public override bool Equals(object? obj) => obj is QueryRef other && Equals(other);
	public override int GetHashCode() => HashCode.Combine(QueryName, Key);
	public override string ToString() => $"{QueryName}({Key})";
}
```

- [ ] **Step 1.4: Implement `Query.cs`**

Create `src/mods/AdventureGuide/src/Incremental/Query.cs`:

```csharp
namespace AdventureGuide.Incremental;

/// <summary>Typed handle for a query registered with an <see cref="Engine{TFactKey}"/>.
/// Opaque to callers; only the engine that created it can read it.</summary>
public sealed class Query<TKey, TValue> where TKey : notnull
{
	internal Query(string name, int id, Func<object, TKey, TValue> compute)
	{
		Name = name;
		Id = id;
		Compute = compute;
	}

	internal string Name { get; }
	internal int Id { get; }
	internal Func<object, TKey, TValue> Compute { get; }
}
```

The `object` parameter in `Compute` carries the `ReadContext<TFactKey>` — kept non-generic here so queries don't leak `TFactKey` into their handle's type.

- [ ] **Step 1.5: Implement `ReadContext.cs`**

Create `src/mods/AdventureGuide/src/Incremental/ReadContext.cs`:

```csharp
namespace AdventureGuide.Incremental;

/// <summary>Passed to every query's compute function. Records fact dependencies
/// explicitly via <see cref="RecordFact"/> and stitches query-to-query
/// dependencies transparently via <see cref="Read"/>.</summary>
public sealed class ReadContext<TFactKey> where TFactKey : notnull
{
	private readonly Engine<TFactKey> _engine;

	internal ReadContext(Engine<TFactKey> engine) => _engine = engine;

	internal HashSet<TFactKey> Facts { get; } = new();
	internal HashSet<(int QueryId, object Key)> QueryDeps { get; } = new();

	public void RecordFact(TFactKey fact) => Facts.Add(fact);

	public TValue Read<TKey, TValue>(Query<TKey, TValue> query, TKey key) where TKey : notnull
	{
		QueryDeps.Add((query.Id, (object)key));
		return _engine.Read(query, key);
	}
}
```

- [ ] **Step 1.6: Implement `Engine.cs`**

Create `src/mods/AdventureGuide/src/Incremental/Engine.cs`:

```csharp
namespace AdventureGuide.Incremental;

/// <summary>Salsa-shaped incremental query engine. Memoises <c>(query, key)</c>
/// entries; recomputes lazily on read when a recorded fact or sub-query dep has
/// a newer revision than the entry. Backdating (value-equality on recomputed
/// outputs) suppresses ripples when a recompute produces an unchanged value.</summary>
public sealed class Engine<TFactKey> where TFactKey : notnull
{
	private int _revision;
	private int _nextQueryId;
	private readonly Dictionary<TFactKey, int> _factRevisions = new();
	private readonly Dictionary<(int, object), Entry> _entries = new();
	private readonly Dictionary<TFactKey, HashSet<(int, object)>> _entriesByFact = new();
	private readonly Stack<(int, object)> _computeStack = new();

	public Query<TKey, TValue> DefineQuery<TKey, TValue>(
		string name,
		Func<ReadContext<TFactKey>, TKey, TValue> compute) where TKey : notnull
	{
		int id = _nextQueryId++;
		return new Query<TKey, TValue>(name, id,
			(ctxObj, key) => compute((ReadContext<TFactKey>)ctxObj, (TKey)key));
	}

	public TValue Read<TKey, TValue>(Query<TKey, TValue> query, TKey key) where TKey : notnull
	{
		var entryKey = (query.Id, (object)key);
		if (_computeStack.Contains(entryKey))
			throw new InvalidOperationException(
				$"Cycle detected: query '{query.Name}' with key '{key}' is already being computed.");

		if (_entries.TryGetValue(entryKey, out var entry) && !IsStale(entry))
			return (TValue)entry.Value!;

		return (TValue)Recompute(query, key, entryKey)!;
	}

	public IReadOnlyCollection<QueryRef> InvalidateFacts(IEnumerable<TFactKey> changed)
	{
		var affected = new HashSet<(int, object)>();
		foreach (var fact in changed)
		{
			_revision++;
			_factRevisions[fact] = _revision;
			if (_entriesByFact.TryGetValue(fact, out var dependents))
				affected.UnionWith(dependents);
		}
		// Dependents of dependents get picked up lazily by IsStale() on next read.

		var refs = new List<QueryRef>(affected.Count);
		foreach (var (queryId, key) in affected)
		{
			if (_entries.TryGetValue((queryId, key), out var entry))
				refs.Add(new QueryRef(entry.QueryName, key));
		}
		return refs;
	}

	private bool IsStale(Entry entry)
	{
		foreach (var fact in entry.Facts)
			if (_factRevisions.TryGetValue(fact, out int rev) && rev > entry.Revision)
				return true;

		foreach (var depKey in entry.QueryDeps)
		{
			var lookupKey = (depKey.QueryId, depKey.Key);
			if (!_entries.TryGetValue(lookupKey, out var depEntry))
				return true;
			if (depEntry.Revision > entry.Revision)
				return true;
			if (IsStale(depEntry))
				return true;
		}
		return false;
	}

	private object? Recompute<TKey, TValue>(Query<TKey, TValue> query, TKey key, (int, object) entryKey)
		where TKey : notnull
	{
		_computeStack.Push(entryKey);
		var ctx = new ReadContext<TFactKey>(this);
		TValue value;
		try
		{
			value = (TValue)query.Compute(ctx, key)!;
		}
		finally
		{
			_computeStack.Pop();
		}

		bool existed = _entries.TryGetValue(entryKey, out var prior);
		bool changed = !existed || !Equals(prior.Value, value);

		// Unsubscribe old fact→entry reverse deps before re-subscribing.
		if (existed)
		{
			foreach (var oldFact in prior.Facts)
				if (_entriesByFact.TryGetValue(oldFact, out var set))
					set.Remove(entryKey);
		}

		int newRevision = changed ? ++_revision : prior.Revision;
		var entry = new Entry(query.Name, ctx.Facts, ctx.QueryDeps, value, newRevision);
		_entries[entryKey] = entry;

		foreach (var fact in ctx.Facts)
		{
			if (!_entriesByFact.TryGetValue(fact, out var set))
				_entriesByFact[fact] = set = new HashSet<(int, object)>();
			set.Add(entryKey);
		}

		return value;
	}

	private sealed class Entry
	{
		public Entry(string queryName, HashSet<TFactKey> facts, HashSet<(int QueryId, object Key)> queryDeps, object? value, int revision)
		{
			QueryName = queryName;
			Facts = facts;
			QueryDeps = queryDeps;
			Value = value;
			Revision = revision;
		}

		public string QueryName { get; }
		public HashSet<TFactKey> Facts { get; }
		public HashSet<(int QueryId, object Key)> QueryDeps { get; }
		public object? Value { get; }
		public int Revision { get; }
	}
}
```

- [ ] **Step 1.7: Run tests and verify all pass**

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj -v quiet -nologo
```

Expected: all existing tests pass + 9 new `EngineTests` pass.

- [ ] **Step 1.8: Commit**

```bash
git add src/mods/AdventureGuide/src/Incremental/ src/mods/AdventureGuide/tests/AdventureGuide.Tests/Incremental/
git commit
```

Commit message subject: `feat(mod): add Salsa-shaped incremental engine in AdventureGuide.Incremental`

Body paragraphs: describe the engine's role (memoise query results, invalidate lazily on fact deltas, backdate ripples by value equality), note the zero-Erenshor-types constraint on the public API, and explain that this commit is pure addition — no existing code consumes it yet.

**Task 1 acceptance:**
- `AdventureGuide.Incremental` namespace exists with `Engine`, `Query`, `ReadContext`, `QueryRef`
- Public API references no Erenshor types
- 9 engine tests green
- Whole suite stays green
- Nothing outside `Incremental/` changed

---

### Task 2: Rename `Guide*` prefix on touched types

**Goal:** Mechanical rename across the mod to drop the unjustified `Guide*` prefix from types Group 1 will soon touch. No behaviour change.

**Files:** ~25 production files and ~15 test files (every file that references `GuideFactKey`, `GuideFactKind`, or `GuideChangeSet`). The rename propagates through the compiler; the executor follows error messages.

- [ ] **Step 2.1: Rename type declarations and filenames**

```bash
git mv src/mods/AdventureGuide/src/State/GuideFactKey.cs src/mods/AdventureGuide/src/State/FactKey.cs
git mv src/mods/AdventureGuide/src/State/GuideChangeSet.cs src/mods/AdventureGuide/src/State/ChangeSet.cs
```

Edit `src/mods/AdventureGuide/src/State/FactKey.cs`:
- `public enum GuideFactKind` → `public enum FactKind`
- `public readonly struct GuideFactKey : IEquatable<GuideFactKey>` → `public readonly struct FactKey : IEquatable<FactKey>`
- Update every method/ctor/parameter type and XML-doc reference accordingly.

Edit `src/mods/AdventureGuide/src/State/ChangeSet.cs`:
- `public sealed class GuideChangeSet` → `public sealed class ChangeSet`
- Every `GuideChangeSet` token in the file → `ChangeSet`
- `IEnumerable<GuideFactKey>` → `IEnumerable<FactKey>` (also in `FreezeFacts`, `ChangedFacts`)

- [ ] **Step 2.2: Propagate the rename via ast-grep**

Run the rename across the entire mod source tree and test tree:

```csharp
// use the ast_edit tool with ops:
// [{pat: "GuideFactKey", out: "FactKey"},
//  {pat: "GuideFactKind", out: "FactKind"},
//  {pat: "GuideChangeSet", out: "ChangeSet"}]
// path: src/mods/AdventureGuide/
// lang: csharp
```

Expected: a large number of replacements across production and test code. All references update in one pass.

- [ ] **Step 2.3: Build and fix any residual issues**

```bash
dotnet build src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj -v quiet -nologo
```

Expected: if any compile errors remain (e.g. string-literal references in reflection-based tests like `LiveStateTrackerTests` that look for `"public GuideChangeSet UpdateFrameState()"`), update those string literals to `"public ChangeSet UpdateFrameState()"` by reading the failing file and editing the matched line.

- [ ] **Step 2.4: Run tests and confirm green**

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo
```

Expected: same number of tests pass as before Task 2 started (284 or whatever the current baseline is). No new tests, no dropped tests.

- [ ] **Step 2.5: Commit**

```bash
git add -A src/mods/AdventureGuide/
git commit
```

Commit message subject: `refactor(mod): drop Guide* prefix from FactKey, FactKind, ChangeSet`

Body paragraphs: explain the naming discipline from the reactive-core spec (§ 6) — the `Guide*` prefix survives only where the simple name collides with a non-mod type; these three don't. Note this is the minimum-touch slice of the discipline riding along with Group 1; untouched `Guide*` types (`GuideConfig`, `GuideWindow`, etc.) stay as-is because their simple names collide with external types.

**Task 2 acceptance:**
- `GuideFactKey`/`GuideFactKind`/`GuideChangeSet` no longer appear in the mod source or test tree
- `FactKey`/`FactKind`/`ChangeSet` appear in their place
- Test count unchanged; all green
- No other file moved

---

### Task 3: `GuideReader` wrapper + typed accessors

**Goal:** Introduce the Erenshor-specific wrapper that binds `Engine<FactKey>` to the mod. Exposes typed accessors per fact kind; internally calls `RecordFact` through a held `ReadContext<FactKey>`. Consumers of queries will talk to `GuideReader`, not the engine directly.

The wrapper has two roles:
1. During query computation, it translates typed fact reads (`ReadInventoryCount("item:flask")`) into `ReadContext<FactKey>.RecordFact(new FactKey(FactKind.InventoryItemCount, "item:flask"))` + a live tracker read.
2. At the top level (Plugin's consume phase), it exposes typed query reads (`ReadQuestResolution(questKey, scene)`) that delegate to `engine.Read`.

These two concerns share an API surface. The wrapper holds both an optional `ReadContext<FactKey>?` (non-null only inside a query compute) and the `Engine<FactKey>` + query handles.

**Files:**
- Create: `src/mods/AdventureGuide/src/State/GuideReader.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/State/GuideReaderTests.cs`

- [ ] **Step 3.1: Write `GuideReader` tests first**

Create `src/mods/AdventureGuide/tests/AdventureGuide.Tests/State/GuideReaderTests.cs`:

```csharp
using AdventureGuide.Incremental;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests.State;

public sealed class GuideReaderTests
{
	[Fact]
	public void ReadInventoryCount_RecordsFactDep_WhenCalledInsideQueryCompute()
	{
		var engine = new Engine<FactKey>();
		var inventory = new FakeInventory();
		inventory.Set("item:flask", 3);

		var reader = new GuideReader(engine, inventory);
		int computeCount = 0;

		var query = engine.DefineQuery<string, int>(
			name: "Count",
			compute: (ctx, key) =>
			{
				reader.AttachContext(ctx);
				try
				{
					computeCount++;
					return reader.ReadInventoryCount(key);
				}
				finally { reader.DetachContext(); }
			});

		Assert.Equal(3, engine.Read(query, "item:flask"));
		Assert.Equal(3, engine.Read(query, "item:flask"));
		Assert.Equal(1, computeCount);

		inventory.Set("item:flask", 7);
		engine.InvalidateFacts(new[] { new FactKey(FactKind.InventoryItemCount, "item:flask") });

		Assert.Equal(7, engine.Read(query, "item:flask"));
		Assert.Equal(2, computeCount);
	}

	[Fact]
	public void ReadInventoryCount_ThrowsIfCalledOutsideQueryCompute()
	{
		var engine = new Engine<FactKey>();
		var reader = new GuideReader(engine, new FakeInventory());

		Assert.Throws<InvalidOperationException>(() => reader.ReadInventoryCount("item:flask"));
	}

	private sealed class FakeInventory : IInventoryFactSource
	{
		private readonly Dictionary<string, int> _counts = new();
		public void Set(string itemId, int count) => _counts[itemId] = count;
		public int GetCount(string itemId) => _counts.TryGetValue(itemId, out int c) ? c : 0;
	}
}
```

- [ ] **Step 3.2: Run tests to verify they fail (compile errors)**

Expected: references to `GuideReader`, `IInventoryFactSource`, etc. are missing.

- [ ] **Step 3.3: Implement `GuideReader`**

Create `src/mods/AdventureGuide/src/State/GuideReader.cs`:

```csharp
using AdventureGuide.Incremental;

namespace AdventureGuide.State;

/// <summary>Erenshor-specific wrapper over <see cref="Engine{TFactKey}"/> with
/// <see cref="FactKey"/>. Typed accessors record the appropriate fact key on
/// the active <see cref="ReadContext{TFactKey}"/> (for deps) and forward to the
/// underlying tracker (for values). Each tracker implements a narrow interface
/// so the wrapper can be unit-tested with fakes.</summary>
public sealed class GuideReader
{
	private readonly Engine<FactKey> _engine;
	private readonly IInventoryFactSource _inventory;
	private ReadContext<FactKey>? _activeContext;

	public GuideReader(Engine<FactKey> engine, IInventoryFactSource inventory)
	{
		_engine = engine;
		_inventory = inventory;
	}

	public Engine<FactKey> Engine => _engine;

	internal void AttachContext(ReadContext<FactKey> ctx) => _activeContext = ctx;
	internal void DetachContext() => _activeContext = null;

	public int ReadInventoryCount(string itemId)
	{
		RequireContext().RecordFact(new FactKey(FactKind.InventoryItemCount, itemId));
		return _inventory.GetCount(itemId);
	}

	// Additional typed accessors (ReadQuestActive, ReadQuestCompleted, ReadScene,
	// ReadSourceState, ReadUnlockItemPossessed, ReadTimeOfDay) follow the same
	// shape and are added in Task 4 as each query needs them.

	private ReadContext<FactKey> RequireContext() =>
		_activeContext ?? throw new InvalidOperationException(
			"GuideReader.Read* called outside a query compute. Use engine.Read at the top level.");
}

public interface IInventoryFactSource
{
	int GetCount(string itemId);
}
```

- [ ] **Step 3.4: Run tests, verify pass**

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj -v quiet -nologo
```

Expected: existing suite green + 2 new `GuideReaderTests` green.

- [ ] **Step 3.5: Commit**

```bash
git add src/mods/AdventureGuide/src/State/GuideReader.cs src/mods/AdventureGuide/src/State/IInventoryFactSource.cs src/mods/AdventureGuide/tests/AdventureGuide.Tests/State/GuideReaderTests.cs
git commit
```

Commit message subject: `feat(mod): add GuideReader wrapping Engine<FactKey> with typed fact accessors`

Body paragraphs: explain the two roles (dep recording during query compute, typed access to the engine at the top level), note that this commit seeds the pattern with `ReadInventoryCount` only; the remaining typed accessors (quest active, quest completed, scene, source state, unlock, time-of-day) are added in Task 4 as each query needs them — avoiding speculative API surface that no query consumes.

**Task 3 acceptance:**
- `GuideReader` exists with `ReadInventoryCount`
- `IInventoryFactSource` interface exists
- Tests verify dep recording inside compute + throw-on-misuse outside compute
- Test suite green
- No existing code touches `GuideReader` yet

---

### Task 4: Define `CompiledTargets`, `BlockingZones`, `NavigableQuests` queries

**Goal:** Three independent queries registered with the engine and readable via `GuideReader`. Each comes with its own tests exercising the query through the engine. No production consumer migrates yet; the queries are pure additions that will be composed in Task 5.

This task adds the remaining typed accessors to `GuideReader` as each query demands them. Follow this pattern: add the fact source interface, add the typed accessor, add the query class, add tests.

**Files:**
- Create: `src/mods/AdventureGuide/src/Resolution/Queries/CompiledTargetsQuery.cs`
- Create: `src/mods/AdventureGuide/src/Resolution/Queries/BlockingZonesQuery.cs`
- Create: `src/mods/AdventureGuide/src/Navigation/Queries/NavigableQuestsQuery.cs`
- Modify: `src/mods/AdventureGuide/src/State/GuideReader.cs` — add fact-source fields, typed accessors for quest-active/completed, scene, source-state
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Resolution/Queries/CompiledTargetsQueryTests.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Resolution/Queries/BlockingZonesQueryTests.cs`
- Create: `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Navigation/Queries/NavigableQuestsQueryTests.cs`

- [ ] **Step 4.1: Read `QuestTargetResolver.Resolve` to confirm scene's role** *(audit pre-req from spec § 7)*

```bash
# Use read tool on QuestTargetResolver.cs, inspect Resolve(...)
```

Expected outcome A: scene is used only as a filter on already-computed targets. Confirms `CompiledTargets` query can be keyed on `questKey` alone.
Expected outcome B: scene is used during frontier emission. Re-key `CompiledTargets` on `(questKey, scene)` — same design, different cache shape, also update this plan's task-4 query signatures in-place.

Record the outcome in your working notes before proceeding.

- [ ] **Step 4.2: Write `CompiledTargetsQuery` tests**

Create `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Resolution/Queries/CompiledTargetsQueryTests.cs`. Use `ResolutionTestFactory` (update as needed) to build a guide with one active quest, assert:
- Reading the query returns the expected compiled targets for an active quest
- Reading twice memoises
- Invalidating `QuestActive(quest)` causes recompute
- Invalidating unrelated fact does not

Mirror the shape of `QuestResolutionServiceTests.QuestResolutionService_ExposesBatchResolveAndAffectedInvalidationApis` for the asserted output.

- [ ] **Step 4.3: Implement `CompiledTargetsQuery`**

Create `src/mods/AdventureGuide/src/Resolution/Queries/CompiledTargetsQuery.cs`:

```csharp
using AdventureGuide.Incremental;
using AdventureGuide.Plan;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution.Queries;

/// <summary>Scene-independent frontier walk + target compilation for one quest.
/// Reads quest-active, quest-completed, inventory, unlock, and source-state
/// facts through the active <see cref="ReadContext{TFactKey}"/>.</summary>
public sealed class CompiledTargetsQuery
{
	private readonly EffectiveFrontier _frontier;
	private readonly QuestTargetResolver _questTargetResolver;
	private readonly CompiledGuideModel _guide;
	private readonly GuideReader _reader;

	public Query<string, CompiledTargetsResult> Query { get; }

	public CompiledTargetsQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		EffectiveFrontier frontier,
		QuestTargetResolver questTargetResolver,
		GuideReader reader)
	{
		_guide = guide;
		_frontier = frontier;
		_questTargetResolver = questTargetResolver;
		_reader = reader;
		Query = engine.DefineQuery<string, CompiledTargetsResult>(
			name: "CompiledTargets",
			compute: Compute);
	}

	private CompiledTargetsResult Compute(ReadContext<FactKey> ctx, string questKey)
	{
		_reader.AttachContext(ctx);
		try
		{
			if (!_guide.TryGetNodeId(questKey, out int questNodeId))
				return CompiledTargetsResult.Empty;

			int questIndex = _guide.FindQuestIndex(questNodeId);
			if (questIndex < 0)
				return CompiledTargetsResult.Empty;

			// RecordFact on the quest-active/completed keys so this query is
			// invalidated when the quest state changes.
			_reader.ReadQuestActive(questKey);
			_reader.ReadQuestCompleted(questKey);

			var frontier = new List<FrontierEntry>();
			_frontier.Resolve(questIndex, frontier, -1, tracer: null);
			var session = new SourceResolver.ResolutionSession();
			// Scene role confirmed by Step 4.1: pass the query's current scene
			// only if scene is an emission input (outcome B); otherwise pass null.
			var targets = _questTargetResolver.Resolve(questIndex, currentScene: null, frontier, session, tracer: null);

			return new CompiledTargetsResult(frontier.ToArray(), targets.ToArray());
		}
		finally { _reader.DetachContext(); }
	}
}

public sealed record CompiledTargetsResult(
	IReadOnlyList<FrontierEntry> Frontier,
	IReadOnlyList<ResolvedTarget> Targets)
{
	public static CompiledTargetsResult Empty { get; } =
		new(Array.Empty<FrontierEntry>(), Array.Empty<ResolvedTarget>());

	public bool Equals(CompiledTargetsResult? other) =>
		other is not null
		&& Frontier.SequenceEqual(other.Frontier)
		&& Targets.SequenceEqual(other.Targets);

	public override int GetHashCode() =>
		HashCode.Combine(Frontier.Count, Targets.Count);
}
```

Add `ReadQuestActive(string questKey)` and `ReadQuestCompleted(string questKey)` to `GuideReader` (same pattern as `ReadInventoryCount`). Add the corresponding `IQuestStateFactSource` interface. `QuestStateTracker` implements it.

- [ ] **Step 4.4: Run `CompiledTargetsQueryTests`, verify green**

- [ ] **Step 4.5: Write `BlockingZonesQuery` tests, implement, run green**

`BlockingZonesQuery` reads `SourceState(zoneLineNodeKey)` for each zone line in the scene plus whatever `ZoneRouter.FindFirstLockedHop` touches. Mirror the logic in `QuestResolutionService.BuildBlockingZoneLineByScene`. Return type is a `record` wrapping `ImmutableDictionary<string, int>` or a custom value-equality wrapper over `IReadOnlyDictionary<string, int>`.

- [ ] **Step 4.6: Write `NavigableQuestsQuery` tests, implement, run green**

`NavigableQuestsQuery` is singleton (key type `Unit`; the engine's cache stores one entry). Aggregates from:
- `_trackerState.TrackedQuests` → `ReadTrackerState` fact
- `_tracker.GetActionableQuestDbNames()` → one `QuestActive(*)` fact per active quest — or a coarser `TrackerAggregate` fact if per-quest granularity is not needed
- `_navSet.Keys` where node type is Quest → via an `INavigationSetFactSource`
- `_tracker.GetImplicitlyAvailableQuestDbNames()` → quest-active facts

Return type: `ImmutableArray<string>` with structural equality (record wrapper if needed).

- [ ] **Step 4.7: Commit**

```bash
git add src/mods/AdventureGuide/src/Resolution/Queries/ src/mods/AdventureGuide/src/Navigation/Queries/ src/mods/AdventureGuide/src/State/GuideReader.cs src/mods/AdventureGuide/src/State/IQuestStateFactSource.cs src/mods/AdventureGuide/src/State/INavigationSetFactSource.cs src/mods/AdventureGuide/tests/
git commit
```

Commit message subject: `feat(mod): define CompiledTargets, BlockingZones, NavigableQuests queries`

Body paragraphs: each query's fact set, the audit pre-req outcome from Step 4.1, note that no production consumer reads these yet (wired in Task 5), note equality discipline on return types.

**Task 4 acceptance:**
- Three query classes registered with the engine; each has a `Query` property exposing the handle
- `GuideReader` has accessors for the fact kinds each query reads
- Each query has its own test file verifying memoisation, invalidation, and backdating
- Test suite green
- No existing production consumer has migrated yet

---

### Task 5: `QuestResolution` composed query + cutover

**Goal:** Compose `CompiledTargets` + `BlockingZones` into `QuestResolution(questKey, scene)`, drop `QuestResolutionRecord` snapshots, wire the engine into `Plugin`, migrate every `QuestResolutionService.ResolveQuest`/`ResolveBatch` caller to `guideReader.ReadQuestResolution`, and delete `QuestResolutionService` + `GuideDependencyEngine` + `GuideDerivedKey` + `GuideDerivedKind`.

This is the largest task. Execute in sub-steps, committing at the end.

**Files touched (approximate):**
- Create: `src/mods/AdventureGuide/src/Resolution/Queries/QuestResolutionQuery.cs`
- Modify: `src/mods/AdventureGuide/src/Resolution/QuestResolutionRecord.cs` — drop `_questPhases`, `_itemCounts` fields and related getters; convert to `record`
- Modify: `src/mods/AdventureGuide/src/State/GuideReader.cs` — add `ReadQuestResolution`, `ReadCompiledTargets`, `ReadBlockingZones`, `ReadNavigableQuests` top-level accessors
- Modify: `src/mods/AdventureGuide/src/Plugin.cs` — construct engine + queries; replace dependency-engine invalidation branch with `engine.InvalidateFacts(changeSet.ChangedFacts)` unconditionally; drop the `SceneChanged` special path (scene is just a fact now)
- Delete: `src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs`
- Delete: `src/mods/AdventureGuide/src/State/GuideDependencyEngine.cs`
- Delete: `src/mods/AdventureGuide/src/State/GuideDerivedKey.cs`
- Modify: every consumer of `QuestResolutionService` — use LSP `references` to enumerate; expected: `SpecTreeProjector`, `TrackerSummaryResolver`, possibly `NavigationTargetResolver`
- Modify: test helpers — `ResolutionTestFactory.BuildService`, `SpecTreeProjectorHarness`, `SnapshotHarness`, `QuestPhaseTrackerFactory`, `QuestPhaseTrackerHarness`, `ZoneRouterHarness` all reference `QuestResolutionService` or `GuideDependencyEngine`
- Delete or rewrite: `QuestResolutionServiceTests.cs`, `QuestResolutionInvalidationTests.cs`, `MaintainedViewDiagnosticsTests.cs` (the parts that touch `service.InvalidateAll`)

Note: `MaintainedViewPlanner` still exists and is still called from `Plugin.Update` and `MarkerComputer.ApplyGuideChangeSet`. Keep it working unchanged — Plan B deletes it. The engine's invalidation runs alongside the planner's full-vs-partial logic this plan; they coexist until Plan B retires the planner. This is not a parallel implementation of the same concept — it's transient coexistence between the old marker path (still driven by planner) and the new resolution path (driven by engine).

- [ ] **Step 5.1: Find every consumer of `QuestResolutionService`**

```bash
# Use lsp references on QuestResolutionService.ResolveQuest and ResolveBatch
```

Record the list of (file, line) citations.

- [ ] **Step 5.2: Write `QuestResolutionQuery` tests**

Create `src/mods/AdventureGuide/tests/AdventureGuide.Tests/Resolution/Queries/QuestResolutionQueryTests.cs`. Assert:
- Composed record holds the frontier + targets + blocking zones for a `(questKey, scene)` pair
- Reading twice memoises
- Invalidating only `QuestActive(quest)` recomputes `CompiledTargets` but **not** `BlockingZones` (verify via separate compute counters on the sub-queries)
- Invalidating only `SourceState(zoneLine)` recomputes `BlockingZones` but not `CompiledTargets`
- If sub-query output is unchanged (backdating suppresses it), the composed `QuestResolution` does not recompute

- [ ] **Step 5.3: Implement `QuestResolutionQuery`**

Create `src/mods/AdventureGuide/src/Resolution/Queries/QuestResolutionQuery.cs`:

```csharp
using AdventureGuide.Incremental;
using AdventureGuide.State;

namespace AdventureGuide.Resolution.Queries;

public sealed class QuestResolutionQuery
{
	private readonly CompiledTargetsQuery _compiledTargets;
	private readonly BlockingZonesQuery _blockingZones;
	private readonly QuestTargetProjector _projector;

	public Query<(string QuestKey, string Scene), QuestResolutionRecord> Query { get; }

	public QuestResolutionQuery(
		Engine<FactKey> engine,
		CompiledTargetsQuery compiledTargets,
		BlockingZonesQuery blockingZones,
		QuestTargetProjector projector)
	{
		_compiledTargets = compiledTargets;
		_blockingZones = blockingZones;
		_projector = projector;
		Query = engine.DefineQuery<(string, string), QuestResolutionRecord>(
			name: "QuestResolution",
			compute: Compute);
	}

	private QuestResolutionRecord Compute(
		ReadContext<FactKey> ctx, (string QuestKey, string Scene) key)
	{
		var compiled = ctx.Read(_compiledTargets.Query, key.QuestKey);
		var blocking = ctx.Read(_blockingZones.Query, key.Scene);

		// NavigationTargets projection stays lazy — the `Func<...>` factory is
		// the same pattern as the old service used.
		Func<IReadOnlyList<ResolvedQuestTarget>> navFactory =
			() => _projector.Project(compiled.Targets, key.Scene);

		return new QuestResolutionRecord(
			key.QuestKey,
			key.Scene,
			questIndex: -1,  // Index is no longer carried on the record; remove if unused after migration.
			compiled.Frontier,
			compiled.Targets,
			navFactory,
			blocking.ByTargetScene);
	}
}
```

Note: inspect `QuestResolutionRecord` consumers (LSP references) for any that read `QuestIndex`. If none, drop that field too.

- [ ] **Step 5.4: Update `QuestResolutionRecord`**

Rewrite as a focused record without phase/item-count snapshots:

```csharp
namespace AdventureGuide.Resolution;

public sealed class QuestResolutionRecord
{
	private readonly Func<IReadOnlyList<ResolvedQuestTarget>> _navigationTargetsFactory;
	private IReadOnlyList<ResolvedQuestTarget>? _navigationTargets;

	public QuestResolutionRecord(
		string questKey,
		string currentScene,
		int questIndex,
		IReadOnlyList<FrontierEntry> frontier,
		IReadOnlyList<ResolvedTarget> compiledTargets,
		Func<IReadOnlyList<ResolvedQuestTarget>> navigationTargetsFactory,
		IReadOnlyDictionary<string, int> blockingZoneLineByScene)
	{
		QuestKey = questKey;
		CurrentScene = currentScene ?? string.Empty;
		QuestIndex = questIndex;
		Frontier = frontier;
		CompiledTargets = compiledTargets;
		_navigationTargetsFactory = navigationTargetsFactory;
		_blockingZoneLineByScene = blockingZoneLineByScene;
	}

	private readonly IReadOnlyDictionary<string, int> _blockingZoneLineByScene;

	public string QuestKey { get; }
	public string CurrentScene { get; }
	public int QuestIndex { get; }
	public IReadOnlyList<FrontierEntry> Frontier { get; }
	public IReadOnlyList<ResolvedTarget> CompiledTargets { get; }

	public IReadOnlyList<ResolvedQuestTarget> NavigationTargets =>
		_navigationTargets ??= _navigationTargetsFactory();

	public bool TryGetBlockingZoneLineNodeId(string? targetScene, out int zoneLineNodeId)
	{
		zoneLineNodeId = default;
		if (string.IsNullOrWhiteSpace(targetScene)) return false;
		return _blockingZoneLineByScene.TryGetValue(targetScene, out zoneLineNodeId);
	}
}
```

**Dropped:** `_questPhases`, `_itemCounts`, `GetQuestPhase`, `IsQuestCompleted`, `GetItemCount`. Callers of these methods (use LSP references) migrate to reading the trackers directly via `_questTracker.IsCompleted(dbName)` / `_questPhaseTracker.GetPhase(index)` / `_questTracker.CountItem(itemIndex)` — the spec's § 2 Q1 resolution explicitly authorises this because the update loop is single-threaded.

- [ ] **Step 5.5: Add `ReadQuestResolution` to `GuideReader` (top-level, not inside compute)**

```csharp
public QuestResolutionRecord ReadQuestResolution(string questKey, string scene)
{
	// Top-level read: no active context, engine manages the compute context.
	return _engine.Read(_questResolutionQuery.Query, (questKey, scene));
}
```

Pass the query handles in through `GuideReader`'s constructor; Plugin constructs the query objects and passes them when building `GuideReader`.

- [ ] **Step 5.6: Wire engine into `Plugin.cs`**

In Plugin's field declarations:
- Add `private Engine<FactKey>? _engine;`
- Add `private CompiledTargetsQuery? _compiledTargetsQuery;` (and the other three)
- Add `private GuideReader? _guideReader;`

In Plugin's initialization path (where `_questResolutionService` is constructed today):
- Construct `_engine = new Engine<FactKey>();`
- Construct each query class with engine + dependencies
- Construct `_guideReader = new GuideReader(engine, invSource, questSource, navSource, sceneSource, sourceStateSource, compiledTargetsQuery, blockingZonesQuery, navigableQuestsQuery, questResolutionQuery)` — adapt to however many dependencies the final design needs

In `Plugin.Update` (L527-L538 from current source):

Replace:
```csharp
if (selectorChangeSet.SceneChanged)
{
    _questResolutionService?.InvalidateAll(selectorChangeSet);
    _zoneRouter?.Rebuild();
}
else if (selectorChangeSet.HasMeaningfulChanges)
{
    var affected = _dependencyEngine?.InvalidateFacts(selectorChangeSet.ChangedFacts)
        ?? new HashSet<GuideDerivedKey>();
    _questResolutionService?.InvalidateAffected(affected);
    _zoneRouter?.ObserveInvalidation(affected);
}
```

With:
```csharp
if (selectorChangeSet.HasMeaningfulChanges)
{
    _engine?.InvalidateFacts(selectorChangeSet.ChangedFacts);
    if (selectorChangeSet.SceneChanged)
        _zoneRouter?.Rebuild();  // Rebuild stays until ZoneRouter is fact-driven (out of scope).
}
```

Scene change flows through `ChangedFacts` (the tracker emits a `FactKey(Scene, "current")`), which the engine invalidates like any other fact. `_questResolutionService?.InvalidateAll` and `.InvalidateAffected` calls disappear with the service itself.

- [ ] **Step 5.7: Migrate every `QuestResolutionService` consumer**

For each citation from Step 5.1, replace the call:

```csharp
// Before
var record = _questResolutionService.ResolveQuest(questKey, currentScene, tracer);

// After
var record = _guideReader.ReadQuestResolution(questKey, currentScene);
```

For `ResolveBatch`, loop at the call site:

```csharp
var records = new Dictionary<string, QuestResolutionRecord>(StringComparer.Ordinal);
foreach (var questKey in questKeys)
    records[questKey] = _guideReader.ReadQuestResolution(questKey, currentScene);
```

Callers that passed an `IResolutionTracer`: the tracer concept is out of scope for the engine. Either keep the tracer threaded through the query compute (add a tracer field to `GuideReader` that's set for the duration of one top-level read, then cleared) or drop tracer support for now if no test or diagnostic currently depends on it during a live session.

- [ ] **Step 5.8: Delete `QuestResolutionService`, `GuideDependencyEngine`, `GuideDerivedKey`**

```bash
git rm src/mods/AdventureGuide/src/Resolution/QuestResolutionService.cs
git rm src/mods/AdventureGuide/src/State/GuideDependencyEngine.cs
git rm src/mods/AdventureGuide/src/State/GuideDerivedKey.cs
```

- [ ] **Step 5.9: Update test helpers**

`ResolutionTestFactory.BuildService` — rename to `BuildReader` (or similar); returns a `GuideReader` backed by an engine and a test harness fact source. Callers that use it update in this same step.

`SpecTreeProjectorHarness`, `SnapshotHarness`, `QuestPhaseTrackerFactory`, `QuestPhaseTrackerHarness`, `ZoneRouterHarness` — each references `GuideDependencyEngine` or `QuestResolutionService`. Replace with `Engine<FactKey>` + `GuideReader` construction.

- [ ] **Step 5.10: Rewrite or delete obsolete test files**

`QuestResolutionServiceTests.cs` — the behaviour it covers (batch resolution, invalidation) is now covered by `QuestResolutionQueryTests` and the engine tests. Delete the file.

`QuestResolutionInvalidationTests.cs` — verifies invalidation of inventory/unlock/quest facts invalidates the cache. Rewrite against `guideReader.ReadQuestResolution` + `engine.InvalidateFacts`. Most assertions survive as-is; the mechanism moves from `service.InvalidateAffected(affectedDerivedKeys)` to `engine.InvalidateFacts(changedFacts)`.

`MaintainedViewDiagnosticsTests.cs` — line 128 calls `service.InvalidateAll(ChangeSet.None)`. This test specifically verifies planner-diagnostics behaviour, which survives Plan A. Replace the line with `engine.InvalidateFacts(ChangeSet.None.ChangedFacts)` or equivalent no-op; the test's scoped assertion is about the planner, not the service.

- [ ] **Step 5.11: Build clean**

```bash
dotnet build src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj -v quiet -nologo
```

Follow compile errors iteratively. Common issues: consumers that imported `AdventureGuide.Resolution.QuestResolutionService` now need to import `AdventureGuide.State.GuideReader` or the query namespaces.

- [ ] **Step 5.12: Run tests, verify green**

```bash
dotnet test src/mods/AdventureGuide/tests/AdventureGuide.Tests/AdventureGuide.Tests.csproj --no-build -v quiet -nologo
```

Expected: ≥ baseline test count, all green. Net change: `QuestResolutionServiceTests` deletions + `QuestResolutionInvalidationTests` rewrite + new `QuestResolutionQueryTests`.

- [ ] **Step 5.13: Deploy and verify in-game**

```bash
uv run erenshor mod deploy --mod adventure-guide --scripts
```

F6 reload in game. Verify:
- Quest tracker UI updates when a quest's phase changes
- Navigation target changes when a quest's active state changes
- Scene change produces fresh resolution (no stale targets from the previous scene)
- Incident dump shows no new `FrameStall` or `FrameHitch`

- [ ] **Step 5.14: Commit**

```bash
git add -A src/mods/AdventureGuide/
git commit
```

Commit message subject: `refactor(mod): route quest resolution through the incremental engine`

Body paragraphs: describe the cutover — QuestResolution becomes a composed engine query built from CompiledTargets + BlockingZones, QuestResolutionRecord sheds its phase/item-count snapshots (consumers read the trackers live under a single-threaded update loop), Plugin no longer branches on scene-changed for cache invalidation because scene is now a fact like any other, and the whole `QuestResolutionService` + `GuideDependencyEngine` + `GuideDerivedKey` triple is deleted because the engine subsumes every role each of them played.

Note that `MaintainedViewPlanner` still exists and is still called during the marker path — Plan B retires it.

**Task 5 acceptance:**
- `QuestResolution` composed query registered and exercised by tests
- `QuestResolutionRecord` has no phase or item-count snapshot fields
- `QuestResolutionService`, `GuideDependencyEngine`, `GuideDerivedKey`, `GuideDerivedKind` are deleted
- Every consumer of the old service reads through `GuideReader.ReadQuestResolution` instead
- Plugin's scene-changed branch is collapsed into the generic fact-invalidation path
- Test suite green; mod builds; in-game deploy confirms no frame-timing regression
- `MaintainedViewPlanner` still present and working (Plan B territory)

---

## Spec Coverage Check

| Spec section | Covered by |
|---|---|
| § 2 Q1 (drop snapshots) | Task 5 |
| § 2 Q5 (retire planner) | **Plan B** |
| § 3 engine | Task 1 |
| § 3.5 equality discipline | Tasks 1, 4, 5 (every query return type is a record with value equality) |
| § 4.1 CompiledTargets | Task 4 |
| § 4.2 BlockingZones | Task 4 |
| § 4.3 NavigableQuests | Task 4 |
| § 4.4 QuestResolution | Task 5 |
| § 4.5 MarkerCandidates | **Plan B** |
| § 5 five-phase orchestrator | **Plan B** |
| § 6 naming discipline | Tasks 1, 2, 3, 4, 5 |
| § 7 extraction-friendliness | Task 1 (generic engine), Task 3 (single-seam wrapper) |
| § 8 audit pre-req | Task 4, Step 4.1 |
| § 9 acceptance criteria | Partial — Plan A hits engine, queries, record-snapshot drop, partial namespace; Plan B finishes |

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-ag-reactive-core-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Task 5's size argues for this — its sub-steps benefit from focused context.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review. Works but tasks 4 and 5 will consume substantial context.

Which approach?
