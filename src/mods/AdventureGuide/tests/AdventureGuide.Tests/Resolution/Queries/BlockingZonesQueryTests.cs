using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Position;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Resolution.Queries;

public sealed class BlockingZonesQueryTests
{
	[Fact]
	public void Read_ReturnsEmpty_WhenNoZonesAreBlocked()
	{
		var fixture = BlockingZonesFixture.Create();
		fixture.UnlockRouteToSceneC();

		var result = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.Empty(result.ByTargetScene);
	}

	[Fact]
	public void Read_Memoizes_WhenNoInvalidationOccurs()
	{
		var fixture = BlockingZonesFixture.Create();

		var first = fixture.Engine.Read(fixture.Query.Query, "SceneA");
		var second = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.Same(first, second);
		Assert.Equal(1, fixture.ComputeCount);
	}

	[Fact]
	public void Read_DoesNotRecompute_WhenUnrelatedSourceStateInvalidates()
	{
		var fixture = BlockingZonesFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "spawn:corpse") });
		var second = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.Same(first, second);
		Assert.Equal(1, fixture.ComputeCount);
	}

	[Fact]
	public void Read_Recomputes_WhenRouteUnlockChanges()
	{
		var fixture = BlockingZonesFixture.Create();
		var before = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		fixture.UnlockRouteToSceneC();
		var after = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.NotSame(before, after);
		Assert.Empty(after.ByTargetScene);
		Assert.Equal(2, fixture.ComputeCount);
	}

	[Fact]
	public void Read_DoesNotRecompute_WhenDisconnectedRouteUnlockChanges()
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "SceneA")
			.AddZone("zone:b", scene: "SceneB")
			.AddZone("zone:c", scene: "SceneC")
			.AddZone("zone:x", scene: "SceneX")
			.AddZone("zone:y", scene: "SceneY")
			.AddZoneLine("zl:ab", scene: "SceneA", destinationZoneKey: "zone:b", x: 10f, y: 0f, z: 0f)
			.AddZoneLine("zl:bc", scene: "SceneB", destinationZoneKey: "zone:c", x: 20f, y: 0f, z: 0f)
			.AddZoneLine("zl:xy", scene: "SceneX", destinationZoneKey: "zone:y", x: 30f, y: 0f, z: 0f)
			.AddItem("item:silver-key")
			.AddItem("item:gold-key")
			.AddEdge("item:silver-key", "zl:bc", EdgeType.UnlocksZoneLine)
			.AddEdge("item:gold-key", "zl:xy", EdgeType.UnlocksZoneLine)
			.Build();
		var fixture = BlockingZonesFixture.CreateForGuide(guide, currentScene: "SceneA");
		var first = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		fixture.AddToInventory("item:gold-key");
		fixture.InvalidateInventoryChange("item:gold-key");
		var second = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.Same(first, second);
		Assert.Equal(1, fixture.ComputeCount);
	}

	[Fact]
	public void Read_Recomputes_WhenAlternativeReachableRouteUnlocks()
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "SceneA")
			.AddZone("zone:b", scene: "SceneB")
			.AddZone("zone:c", scene: "SceneC")
			.AddZone("zone:d", scene: "SceneD")
			.AddZoneLine("zl:ab", scene: "SceneA", destinationZoneKey: "zone:b", x: 10f, y: 0f, z: 0f)
			.AddZoneLine("zl:ac", scene: "SceneA", destinationZoneKey: "zone:c", x: 11f, y: 0f, z: 0f)
			.AddZoneLine("zl:bd", scene: "SceneB", destinationZoneKey: "zone:d", x: 20f, y: 0f, z: 0f)
			.AddZoneLine("zl:cd", scene: "SceneC", destinationZoneKey: "zone:d", x: 21f, y: 0f, z: 0f)
			.AddItem("item:silver-key")
			.AddItem("item:gold-key")
			.AddEdge("item:silver-key", "zl:bd", EdgeType.UnlocksZoneLine)
			.AddEdge("item:gold-key", "zl:cd", EdgeType.UnlocksZoneLine)
			.Build();
		var fixture = BlockingZonesFixture.CreateForGuide(guide, currentScene: "SceneA");
		var before = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		fixture.AddToInventory("item:gold-key");
		fixture.InvalidateInventoryChange("item:gold-key");
		var after = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.NotSame(before, after);
		Assert.DoesNotContain("SceneD", after.ByTargetScene.Keys);
		Assert.Equal(2, fixture.ComputeCount);
	}

	private sealed class BlockingZonesFixture
	{
		private readonly HashSet<string> _inventory = new(StringComparer.Ordinal);

		private BlockingZonesFixture(
			Engine<FactKey> engine,
			BlockingZonesQuery query,
			ZoneRouterHarness? harness,
			QuestStateTracker? tracker,
			ZoneRouter? router)
		{
			Engine = engine;
			Query = query;
			Harness = harness;
			Tracker = tracker;
			Router = router;
		}

		public Engine<FactKey> Engine { get; }
		public BlockingZonesQuery Query { get; }
		public ZoneRouterHarness? Harness { get; }
		public QuestStateTracker? Tracker { get; }
		public ZoneRouter? Router { get; }
		public long ComputeCount => Engine.GetStatistics().PerQuery["BlockingZones"].Computes;

		public static BlockingZonesFixture Create()
		{
			var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");
			var engine = new Engine<FactKey>();
			return new BlockingZonesFixture(
				engine,
				new BlockingZonesQuery(engine, harness.Guide, router),
				harness,
				null,
				null
			);
		}

		public static BlockingZonesFixture CreateForGuide(
			AdventureGuide.CompiledGuide.CompiledGuide guide,
			string currentScene,
			params string[] inventoryItemKeys)
		{
			var tracker = new QuestStateTracker(guide);
			var inventoryCounts = inventoryItemKeys.ToDictionary(key => key, _ => 1, StringComparer.Ordinal);
			tracker.LoadState(
				currentZone: currentScene,
				activeQuests: Array.Empty<string>(),
				completedQuests: Array.Empty<string>(),
				inventoryCounts: inventoryCounts,
				keyringItemKeys: Array.Empty<string>()
			);

			var gameState = new GameState(guide);
			gameState.Register(NodeType.Quest, NodeStateResolvers.Quest(tracker));
			gameState.Register(NodeType.Item, NodeStateResolvers.Item(tracker));

			var unlocks = new UnlockEvaluator(guide, gameState, tracker);
			gameState.Register(NodeType.ZoneLine, NodeStateResolvers.ZoneLine(unlocks));

			var router = new ZoneRouter(guide, unlocks);
			var engine = new Engine<FactKey>();
			var fixture = new BlockingZonesFixture(
				engine,
				new BlockingZonesQuery(engine, guide, router),
				null,
				tracker,
				router
			);
			foreach (var inventoryItemKey in inventoryItemKeys)
				fixture._inventory.Add(inventoryItemKey);
			return fixture;
		}

		public void AddToInventory(string itemKey)
		{
			if (Harness != null)
			{
				Harness.AddToInventory(itemKey);
				return;
			}

			Assert.NotNull(Tracker);
			_inventory.Add(itemKey);
			Tracker!.LoadState(
				currentZone: "SceneA",
				activeQuests: Array.Empty<string>(),
				completedQuests: Array.Empty<string>(),
				inventoryCounts: _inventory.ToDictionary(key => key, _ => 1, StringComparer.Ordinal),
				keyringItemKeys: Array.Empty<string>()
			);
		}

		public void InvalidateInventoryChange(string itemKey)
		{
			if (Harness != null)
			{
				var changeSet = Harness.ForInventoryChange(itemKey);
				Engine.InvalidateFacts(changeSet.ChangedFacts);
				Harness.Router.ObserveInvalidation(changeSet.ChangedFacts);
				return;
			}

			Assert.NotNull(Router);
			var changedFacts = BuildInventoryFacts(itemKey);
			Engine.InvalidateFacts(changedFacts);
			Router!.ObserveInvalidation(changedFacts);
		}

		public void UnlockRouteToSceneC()
		{
			AddToInventory("item:silver-key");
			InvalidateInventoryChange("item:silver-key");
		}

		private static IReadOnlyCollection<FactKey> BuildInventoryFacts(string itemKey)
		{
			var facts = new List<FactKey> { new(FactKind.InventoryItemCount, itemKey) };
			if (itemKey is "item:silver-key" or "item:gold-key")
				facts.Add(new FactKey(FactKind.UnlockItemPossessed, itemKey));
			return facts;
		}
	}
}
