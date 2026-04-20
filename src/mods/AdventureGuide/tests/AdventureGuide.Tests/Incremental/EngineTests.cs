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

	private sealed class Box : IEquatable<Box>
	{
		public Box(int payload) => Payload = payload;
		public int Payload { get; }
		public bool Equals(Box? other) => other is not null && other.Payload == Payload;
		public override bool Equals(object? obj) => Equals(obj as Box);
		public override int GetHashCode() => Payload;
	}
}
