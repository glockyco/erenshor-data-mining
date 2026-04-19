using AdventureGuide.Incremental;
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
	}

	[Fact]
	public void Read_Recomputes_WhenSourceStateWildcardInvalidatesEntry()
	{
		var fixture = BlockingZonesFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "*") });
		var second = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.NotSame(first, second);
		Assert.Equal(first, second);
	}

	[Fact]
	public void Read_DoesNotRecompute_WhenUnrelatedFactInvalidates()
	{
		var fixture = BlockingZonesFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "ROOT") });
		var second = fixture.Engine.Read(fixture.Query.Query, "SceneA");

		Assert.Same(first, second);
	}

	private sealed class BlockingZonesFixture
	{
		private BlockingZonesFixture(
			Engine<FactKey> engine,
			BlockingZonesQuery query,
			ZoneRouterHarness harness)
		{
			Engine = engine;
			Query = query;
			Harness = harness;
		}

		public Engine<FactKey> Engine { get; }
		public BlockingZonesQuery Query { get; }
		public ZoneRouterHarness Harness { get; }

		public static BlockingZonesFixture Create()
		{
			var (router, harness) = ZoneRouterHarness.BuildWithZoneLineUnlockedBy("item:silver-key");
			var engine = new Engine<FactKey>();
			return new BlockingZonesFixture(
				engine,
				new BlockingZonesQuery(engine, harness.Guide, router),
				harness);
		}

		public void UnlockRouteToSceneC()
		{
			Harness.AddToInventory("item:silver-key");
			var changeSet = Harness.ForInventoryChange("item:silver-key", Array.Empty<string>());
			Harness.Router.ObserveInvalidation(Harness.DependencyEngine.InvalidateFacts(changeSet.ChangedFacts));
		}
	}
}
