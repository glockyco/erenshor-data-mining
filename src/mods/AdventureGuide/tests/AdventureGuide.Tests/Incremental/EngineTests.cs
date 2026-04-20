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

	[Fact]
	public void Read_ThrowsWhenQueryBelongsToDifferentEngine()
	{
		var engineA = new Engine<TestFact>();
		var engineB = new Engine<TestFact>();
		var queryFromA = engineA.DefineQuery<int, int>(name: "Q", compute: (ctx, key) => key);

		Assert.Throws<InvalidOperationException>(() => engineB.Read(queryFromA, 0));
	}

	[Fact]
	public void Backdating_PreservesReferenceIdentity_WhenValueUnchanged()
	{
		var engine = new Engine<TestFact>();
		var fact = new TestFact("source");
		var value = new Box(42);

		var query = engine.DefineQuery<int, Box>(
			name: "Source",
			compute: (ctx, key) => { ctx.RecordFact(fact); return new Box(value.Payload); });

		var first = engine.Read(query, 0);
		engine.InvalidateFacts(new[] { fact });
		var second = engine.Read(query, 0);

		Assert.Same(first, second);
	}

	[Fact]
	public void Read_SkipsRecompute_WhenEntryAlreadyVerifiedForBumpedFact()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var fact = new TestFact("source");
		int sourceValue = 42;

		var query = engine.DefineQuery<int, int>(
			name: "Source",
			compute: (ctx, key) => { computeCount++; ctx.RecordFact(fact); return sourceValue; });

		engine.Read(query, 0);
		Assert.Equal(1, computeCount);

		// One invalidation, many reads. Before verified-at-tick, every read after
		// the bump ran compute. After the fix, one recompute verifies the entry
		// against the bumped fact's revision and subsequent reads skip.
		engine.InvalidateFacts(new[] { fact });
		engine.Read(query, 0);
		engine.Read(query, 0);
		engine.Read(query, 0);

		Assert.Equal(2, computeCount);
	}

	[Fact]
	public void Unsubscribing_RemovesEmptyFactSet_FromEntriesByFact()
	{
		var engine = new Engine<TestFact>();
		var factA = new TestFact("A");
		var factB = new TestFact("B");
		bool readA = true;

		var query = engine.DefineQuery<int, int>(
			name: "Switcher",
			compute: (ctx, key) =>
			{
				ctx.RecordFact(readA ? factA : factB);
				return readA ? 1 : 2;
			});

		engine.Read(query, 0);
		Assert.True(engine.EntriesByFactForTests.ContainsKey(factA));

		readA = false;
		engine.InvalidateFacts(new[] { factA });
		engine.Read(query, 0);

		Assert.False(engine.EntriesByFactForTests.ContainsKey(factA));
		Assert.True(engine.EntriesByFactForTests.ContainsKey(factB));
	}

	[Fact]
	public void InvalidateFacts_DuringCompute_Throws()
	{
		var engine = new Engine<TestFact>();
		var fact = new TestFact("source");

		var query = engine.DefineQuery<int, int>(
			name: "Reentrant",
			compute: (ctx, key) =>
			{
				ctx.RecordFact(fact);
				engine.InvalidateFacts(new[] { fact });
				return 0;
			});

		Assert.Throws<InvalidOperationException>(() => engine.Read(query, 0));
	}

	[Fact]
	public void DefineQuery_WithDuplicateName_Throws()
	{
		var engine = new Engine<TestFact>();
		engine.DefineQuery<int, int>(name: "Q", compute: (ctx, key) => key);

		Assert.Throws<InvalidOperationException>(() =>
			engine.DefineQuery<int, int>(name: "Q", compute: (ctx, key) => key + 1));
	}

	[Fact]
	public void TryPeek_DoesNotRecompute_EvenIfStale()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var fact = new TestFact("source");
		var query = engine.DefineQuery<int, int>(
			name: "Peek",
			compute: (ctx, key) => { computeCount++; ctx.RecordFact(fact); return key; });

		engine.Read(query, 7);
		Assert.Equal(1, computeCount);

		engine.InvalidateFacts(new[] { fact });
		Assert.True(engine.TryPeek(query, 7, out int peeked));
		Assert.Equal(7, peeked);
		Assert.Equal(1, computeCount);
	}

	[Fact]
	public void TryPeek_ReturnsFalse_WhenEntryMissing()
	{
		var engine = new Engine<TestFact>();
		var query = engine.DefineQuery<int, int>(name: "Peek", compute: (ctx, key) => key);

		Assert.False(engine.TryPeek(query, 0, out int _));
	}

	[Fact]
	public void Evict_RemovesEntry_AndSubscriptions()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var fact = new TestFact("source");
		var query = engine.DefineQuery<int, int>(
			name: "Evict",
			compute: (ctx, key) => { computeCount++; ctx.RecordFact(fact); return key; });

		engine.Read(query, 0);
		Assert.True(engine.EntriesByFactForTests.ContainsKey(fact));

		Assert.True(engine.Evict(query, 0));
		Assert.False(engine.EntriesByFactForTests.ContainsKey(fact));

		engine.Read(query, 0);
		Assert.Equal(2, computeCount);
	}

	[Fact]
	public void EvictQuery_RemovesAllEntriesForQuery()
	{
		var engine = new Engine<TestFact>();
		var fact = new TestFact("source");
		var query = engine.DefineQuery<int, int>(
			name: "EvictAll",
			compute: (ctx, key) => { ctx.RecordFact(fact); return key; });

		engine.Read(query, 0);
		engine.Read(query, 1);
		engine.Read(query, 2);

		Assert.Equal(3, engine.EvictQuery(query));
		Assert.False(engine.EntriesByFactForTests.ContainsKey(fact));
	}

	[Fact]
	public void Reset_ClearsAllState_AndPreservesDefinitions()
	{
		var engine = new Engine<TestFact>();
		int computeCount = 0;
		var fact = new TestFact("source");
		var query = engine.DefineQuery<int, int>(
			name: "Reset",
			compute: (ctx, key) => { computeCount++; ctx.RecordFact(fact); return key; });

		engine.Read(query, 0);
		Assert.Equal(1, computeCount);

		engine.Reset();
		Assert.Equal(0, engine.Revision);
		Assert.False(engine.EntriesByFactForTests.ContainsKey(fact));

		engine.Read(query, 0);
		Assert.Equal(2, computeCount);
	}

	[Fact]
	public void Statistics_RecordsComputeBackdateStaleFreshCounts()
	{
		var engine = new Engine<TestFact>();
		var fact = new TestFact("source");
		int sourceValue = 42;
		var query = engine.DefineQuery<int, int>(
			name: "S",
			compute: (ctx, key) => { ctx.RecordFact(fact); return sourceValue; });

		engine.Read(query, 0);
		engine.Read(query, 0);
		engine.InvalidateFacts(new[] { fact });
		engine.Read(query, 0);

		var s = engine.GetStatistics();
		Assert.Equal(2, s.TotalComputes);
		Assert.Equal(1, s.TotalBackdates);
		Assert.Equal(2, s.TotalStaleReads);
		Assert.Equal(1, s.TotalFreshReads);
		Assert.Equal(1, s.TotalInvalidations);
		Assert.Equal(1, s.EntryCount);

		var q = s.PerQuery["S"];
		Assert.Equal(2, q.Computes);
		Assert.Equal(1, q.Backdates);
		Assert.Equal(2, q.StaleReads);
		Assert.Equal(1, q.FreshReads);
	}

	[Fact]
	public void Tracer_IsCalledOnRecomputeAndInvalidate()
	{
		var engine = new Engine<TestFact>();
		var fact = new TestFact("source");
		var query = engine.DefineQuery<int, int>(
			name: "T",
			compute: (ctx, key) => { ctx.RecordFact(fact); return key; });

		var tracer = new RecordingTracer();
		engine.SetTracer(tracer);

		engine.Read(query, 5);
		engine.InvalidateFacts(new[] { fact });
		engine.Read(query, 5);

		Assert.Equal(2, tracer.Recomputes.Count);
		Assert.Equal("T", tracer.Recomputes[0].QueryName);
		Assert.False(tracer.Recomputes[0].Backdated);
		Assert.True(tracer.Recomputes[1].Backdated);
		Assert.Single(tracer.Invalidations);
		Assert.Equal(1, tracer.Invalidations[0].DirectAffected);
	}

	private sealed class RecordingTracer : IEngineTracer<TestFact>
	{
		public List<(string QueryName, object Key, bool Backdated, long Ticks)> Recomputes { get; } = new();
		public List<(IReadOnlyCollection<TestFact> Facts, int DirectAffected)> Invalidations { get; } = new();

		public void OnRecompute(string queryName, object key, bool backdated, long computeTicks) =>
			Recomputes.Add((queryName, key, backdated, computeTicks));

		public void OnInvalidate(IReadOnlyCollection<TestFact> facts, int directAffected) =>
			Invalidations.Add((facts, directAffected));
	}

	private sealed class Box : IEquatable<Box>
	{
		public Box(int payload) => Payload = payload;
		public int Payload { get; }
		public bool Equals(Box? other) => other is not null && other.Payload == Payload;
		public override bool Equals(object? obj) => Equals(obj as Box);
		public override int GetHashCode() => Payload;
	}
}
