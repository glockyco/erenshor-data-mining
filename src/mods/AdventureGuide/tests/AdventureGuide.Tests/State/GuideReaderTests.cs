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
			compute: (_, key) =>
			{
				computeCount++;
				return reader.ReadInventoryCount(key);
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

	[Fact]
	public void ReadMarkerCandidates_ThrowsIfQueryIsNotWired()
	{
		var engine = new Engine<FactKey>();
		var reader = new GuideReader(engine, new FakeInventory());

		Assert.Throws<InvalidOperationException>(() => reader.ReadMarkerCandidates("Town"));
	}

	private sealed class FakeInventory : IInventoryFactSource
	{
		private readonly Dictionary<string, int> _counts = new();
		public void Set(string itemId, int count) => _counts[itemId] = count;
		public int GetCount(string itemId) => _counts.TryGetValue(itemId, out int c) ? c : 0;
	}
}
