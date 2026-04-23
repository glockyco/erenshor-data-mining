using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Position;
using AdventureGuide.Position.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Position.Queries;

public sealed class ZoneLineAccessibilityQueryTests
{
	[Fact]
	public void Read_ReturnsInaccessible_ForMissingOrNonZoneLineKeys()
	{
		var fixture = ZoneLineAccessibilityFixture.Create();

		var missing = fixture.Engine.Read(fixture.Query.Query, "zl:missing");
		var nonZoneLine = fixture.Engine.Read(fixture.Query.Query, "item:silver-key");

		Assert.False(missing.IsAccessible);
		Assert.False(nonZoneLine.IsAccessible);
	}

	[Fact]
	public void Read_DoesNotRecompute_WhenUnrelatedSourceStateInvalidates()
	{
		var fixture = ZoneLineAccessibilityFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, "zl:bc");

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "spawn:corpse") });
		var second = fixture.Engine.Read(fixture.Query.Query, "zl:bc");

		Assert.Same(first, second);
		Assert.Equal(1, fixture.ComputeCount);
	}

	[Fact]
	public void Read_Backdates_WhenUnlockFactInvalidatesWithoutChangingAccessibility()
	{
		var fixture = ZoneLineAccessibilityFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, "zl:bc");

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.UnlockItemPossessed, "item:silver-key") });
		var second = fixture.Engine.Read(fixture.Query.Query, "zl:bc");

		Assert.Same(first, second);
		Assert.Equal(2, fixture.ComputeCount);
	}

	[Fact]
	public void Read_ReturnsAccessible_AfterUnlockItemPossessionChanges()
	{
		var fixture = ZoneLineAccessibilityFixture.Create();
		var before = fixture.Engine.Read(fixture.Query.Query, "zl:bc");

		fixture.UnlockRouteToSceneC();
		var after = fixture.Engine.Read(fixture.Query.Query, "zl:bc");

		Assert.False(before.IsAccessible);
		Assert.True(after.IsAccessible);
		Assert.Equal(2, fixture.ComputeCount);
	}

	[Fact]
	public void Read_ReportsParallelAccessibleZoneLinesIndependently_WhenDestinationMatches() {
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "SceneA")
			.AddZone("zone:b", scene: "SceneB")
			.AddZoneLine(
				"zl:ab-silver",
				scene: "SceneA",
				destinationZoneKey: "zone:b",
				x: 10f,
				y: 0f,
				z: 0f
			)
			.AddZoneLine(
				"zl:ab-gold",
				scene: "SceneA",
				destinationZoneKey: "zone:b",
				x: 11f,
				y: 0f,
				z: 0f
			)
			.AddItem("item:silver-key")
			.AddItem("item:gold-key")
			.AddEdge("item:silver-key", "zl:ab-silver", EdgeType.UnlocksZoneLine)
			.AddEdge("item:gold-key", "zl:ab-gold", EdgeType.UnlocksZoneLine)
			.Build();
		var fixture = ZoneLineAccessibilityFixture.CreateForGuide(
			guide,
			currentScene: "SceneA",
			"item:silver-key",
			"item:gold-key"
		);

		var silver = fixture.Engine.Read(fixture.Query.Query, "zl:ab-silver");
		var gold = fixture.Engine.Read(fixture.Query.Query, "zl:ab-gold");

		Assert.True(silver.IsAccessible);
		Assert.True(gold.IsAccessible);
	}

	private sealed class ZoneLineAccessibilityFixture
	{
		private ZoneLineAccessibilityFixture(
			Engine<FactKey> engine,
			ZoneLineAccessibilityQuery query,
			ZoneRouterHarness? harness)
		{
			Engine = engine;
			Query = query;
			Harness = harness;
		}

		public Engine<FactKey> Engine { get; }
		public ZoneLineAccessibilityQuery Query { get; }
		public ZoneRouterHarness? Harness { get; }
		public long ComputeCount => Engine.GetStatistics().PerQuery["ZoneLineAccessibility"].Computes;

		public static ZoneLineAccessibilityFixture Create()
		{
			var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");
			var engine = new Engine<FactKey>();
			return new ZoneLineAccessibilityFixture(
				engine,
				new ZoneLineAccessibilityQuery(engine, harness.Guide, router),
				harness
			);
		}

		public static ZoneLineAccessibilityFixture CreateForGuide(
			AdventureGuide.CompiledGuide.CompiledGuide guide,
			string currentScene,
			params string[] inventoryItemKeys)
		{
			var tracker = new QuestStateTracker(guide);
			tracker.LoadState(
				currentZone: currentScene,
				activeQuests: Array.Empty<string>(),
				completedQuests: Array.Empty<string>(),
				inventoryCounts: inventoryItemKeys.ToDictionary(key => key, _ => 1, StringComparer.Ordinal),
				keyringItemKeys: Array.Empty<string>()
			);

			var gameState = new GameState(guide);
			gameState.Register(NodeType.Quest, NodeStateResolvers.Quest(tracker));
			gameState.Register(NodeType.Item, NodeStateResolvers.Item(tracker));

			var unlocks = new UnlockEvaluator(guide, gameState, tracker);
			gameState.Register(NodeType.ZoneLine, NodeStateResolvers.ZoneLine(unlocks));

			var router = new ZoneRouter(guide, unlocks);
			var engine = new Engine<FactKey>();
			return new ZoneLineAccessibilityFixture(
				engine,
				new ZoneLineAccessibilityQuery(engine, guide, router),
				null
			);
		}

		public void UnlockRouteToSceneC()
		{
			Assert.NotNull(Harness);
			Harness!.AddToInventory("item:silver-key");
			Engine.InvalidateFacts(Harness.ForInventoryChange("item:silver-key").ChangedFacts);
			Harness.Router.ObserveInvalidation(Harness.ForInventoryChange("item:silver-key").ChangedFacts);
		}
	}
}
