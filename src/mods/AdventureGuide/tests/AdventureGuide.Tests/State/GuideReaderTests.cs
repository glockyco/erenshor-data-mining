using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Markers;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
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

	[Fact]
	public void ReadSourceCategory_RecordsSourceFactKeysFromSourceState()
	{
		var engine = new Engine<FactKey>();
		var sourceState = new FakeSourceState();
		var reader = new GuideReader(
			engine,
			new FakeInventory(),
			new FakeQuestState(),
			new FakeTrackerState(),
			new FakeNavigationSet(),
			sourceState);
		var character = new Node { Key = "char:leaf", Type = NodeType.Character };
		sourceState.Categories["char:leaf"] = SpawnCategory.Alive;
		sourceState.SourceFactKeys["char:leaf"] = new[] { "spawn:leaf" };
		int computeCount = 0;
		var query = engine.DefineQuery<Unit, SpawnCategory>(
			"SourceCategory",
			(_, _) =>
			{
				computeCount++;
				return reader.ReadSourceCategory(character);
			});

		Assert.Equal(SpawnCategory.Alive, engine.Read(query, Unit.Value));
		engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "char:leaf") });
		Assert.Equal(SpawnCategory.Alive, engine.Read(query, Unit.Value));
		Assert.Equal(1, computeCount);

		sourceState.Categories["char:leaf"] = SpawnCategory.Dead;
		engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "spawn:leaf") });

		Assert.Equal(SpawnCategory.Dead, engine.Read(query, Unit.Value));
		Assert.Equal(2, computeCount);
	}

	[Fact]
	public void TryGetCachedAvailability_RecordsSourceFactForMiningAndItemBagNodes()
	{
		var guide = new CompiledGuideBuilder()
			.AddMiningNode("mine:iron", scene: "Town", x: 1f, y: 2f, z: 3f)
			.AddItemBag("bag:cache", scene: "Town")
			.Build();
		var tracker = new QuestStateTracker(guide);
		var unlocks = new UnlockEvaluator(guide, new GameState(guide), tracker);
		var liveState = new LiveStateTracker(guide, unlocks);
		var engine = new Engine<FactKey>();
		var miningNode = guide.GetNode("mine:iron")!;
		var itemBagNode = guide.GetNode("bag:cache")!;
		int computeCount = 0;
		var query = engine.DefineQuery<Unit, int>(
			"CachedAvailability",
			(_, _) =>
			{
				computeCount++;
				liveState.TryGetCachedMiningAvailability(miningNode, out _);
				liveState.TryGetCachedItemBagAvailability(itemBagNode, out _);
				return computeCount;
			});

		Assert.Equal(1, engine.Read(query, Unit.Value));
		Assert.Equal(1, engine.Read(query, Unit.Value));

		engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "mine:iron") });
		Assert.Equal(2, engine.Read(query, Unit.Value));

		engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "bag:cache") });
		Assert.Equal(3, engine.Read(query, Unit.Value));
	}

	private sealed class FakeInventory : IInventoryFactSource
	{
		private readonly Dictionary<string, int> _counts = new();
		public void Set(string itemId, int count) => _counts[itemId] = count;
		public int GetCount(string itemId) => _counts.TryGetValue(itemId, out int c) ? c : 0;
	}

	private sealed class FakeQuestState : IQuestStateFactSource
	{
		public string CurrentScene => "Town";
		public bool IsActive(string dbName) => false;
		public bool IsCompleted(string dbName) => false;
		public IEnumerable<string> GetActionableQuestDbNames() => Array.Empty<string>();
		public IEnumerable<string> GetImplicitlyAvailableQuestDbNames() => Array.Empty<string>();
	}

	private sealed class FakeTrackerState : ITrackerStateFactSource
	{
		public IReadOnlyList<string> TrackedQuests => Array.Empty<string>();
	}

	private sealed class FakeNavigationSet : INavigationSetFactSource
	{
		public IReadOnlyCollection<string> Keys => Array.Empty<string>();
	}

	private sealed class FakeSourceState : ISourceStateFactSource
	{
		public Dictionary<string, SpawnCategory> Categories { get; } = new(StringComparer.Ordinal);
		public Dictionary<string, IReadOnlyCollection<string>> SourceFactKeys { get; } = new(StringComparer.Ordinal);

		public SpawnCategory GetCategory(Node node) =>
			Categories.TryGetValue(node.Key, out var category) ? category : SpawnCategory.NotApplicable;

		public IReadOnlyCollection<string> GetSourceFactKeys(Node node) =>
			SourceFactKeys.TryGetValue(node.Key, out var keys) ? keys : new[] { node.Key };
	}
}
