using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Frontier;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Resolution.Queries;

public sealed class CompiledTargetsQueryTests
{
	[Fact]
	public void Read_ReturnsCompiledTargetsForActiveQuest()
	{
		var fixture = CompiledTargetsFixture.Create();

		var result = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Single(result.Frontier);
		Assert.Single(result.Targets);
		Assert.Equal("char:leaf", fixture.Guide.GetNodeKey(result.Targets[0].TargetNodeId));
	}

	[Fact]
	public void Read_Memoizes_WhenNoInvalidationOccurs()
	{
		var fixture = CompiledTargetsFixture.Create();

		var first = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));
		var second = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Same(first, second);
	}

	[Fact]
	public void Read_Recomputes_WhenQuestActiveFactInvalidatesEntry()
	{
		var fixture = CompiledTargetsFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "ROOT") });
		var second = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Equal(first, second);
	}

	[Fact]
	public void Read_DoesNotRecompute_WhenUnrelatedFactInvalidates()
	{
		var fixture = CompiledTargetsFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.InventoryItemCount, "item:other") });
		var second = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Same(first, second);
	}

	private sealed class CompiledTargetsFixture
	{
		private CompiledTargetsFixture(
			AdventureGuide.CompiledGuide.CompiledGuide guide,
			Engine<FactKey> engine,
			CompiledTargetsQuery query)
		{
			Guide = guide;
			Engine = engine;
			Query = query;
		}

		public AdventureGuide.CompiledGuide.CompiledGuide Guide { get; }
		public Engine<FactKey> Engine { get; }
		public CompiledTargetsQuery Query { get; }

		public static CompiledTargetsFixture Create()
		{
			var guide = new CompiledGuideBuilder()
				.AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
				.AddItem("item:root")
				.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:root", 1) })
				.AddItemSource(
					"item:root",
					"char:leaf",
					edgeType: (byte)EdgeType.DropsItem,
					sourceType: (byte)NodeType.Character)
				.Build();
			var phases = new QuestPhaseTracker(guide);
			phases.Initialize(
				Array.Empty<string>(),
				new[] { "ROOT" },
				new Dictionary<string, int>(),
				Array.Empty<string>());
			var frontier = new EffectiveFrontier(guide, phases);
			var sourceResolver = new SourceResolver(
				guide,
				phases,
				new UnlockPredicateEvaluator(guide, phases),
				new StubLivePositionProvider(),
				TestPositionResolvers.Create(guide));
			var resolver = new QuestTargetResolver(guide, frontier, sourceResolver, zoneRouter: null);
			var engine = new Engine<FactKey>();
			var reader = new GuideReader(
				engine,
				new FakeInventory(),
				new FakeQuestState(currentScene: "Town"),
				new FakeTrackerState(),
				new FakeNavigationSet());

			return new CompiledTargetsFixture(
				guide,
				engine,
				new CompiledTargetsQuery(engine, guide, frontier, resolver, reader));
		}
	}

	private sealed class FakeInventory : IInventoryFactSource
	{
		public int GetCount(string itemId) => 0;
	}

	private sealed class FakeQuestState : IQuestStateFactSource
	{
		public FakeQuestState(string currentScene) => CurrentScene = currentScene;

		public string CurrentScene { get; }
		public bool IsActive(string dbName) => string.Equals(dbName, "ROOT", StringComparison.OrdinalIgnoreCase);
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
}
