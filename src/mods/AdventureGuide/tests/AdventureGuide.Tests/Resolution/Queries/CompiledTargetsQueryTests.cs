using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Frontier;
using AdventureGuide.Navigation;
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

	[Fact]
	public void Read_CreatesFreshResolutionSessionPerRecompute()
	{
		var fixture = CompiledTargetsFixture.Create();

		fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));
		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "ROOT") });
		fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Equal(2, fixture.UsedSessions.Count);
		Assert.NotSame(fixture.UsedSessions[0], fixture.UsedSessions[1]);
	}

	[Fact]
	public void Read_UsesFreshResolutionSessionWithinEachRecompute()
	{
		var fixture = CompiledTargetsFixture.Create();

		fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));
		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "ROOT") });
		fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Equal(2, fixture.UsedSessions.Count);
		Assert.NotSame(fixture.UsedSessions[0], fixture.UsedSessions[1]);
	}

	[Fact]
	public void Read_ReturnsPrerequisiteTargets_WhenRequiredItemSourceIsQuestLocked()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:eye")
			.AddItem("item:ring")
			.AddCharacter("char:plax", scene: "Stowaway", x: 10f, y: 0f, z: 20f)
			.AddCharacter("char:liani", scene: "Azure", x: 1f, y: 0f, z: 2f)
			.AddItemSource(
				"item:eye",
				"char:plax",
				edgeType: (byte)EdgeType.DropsItem,
				sourceType: (byte)NodeType.Character)
			.AddItemSource(
				"item:ring",
				"char:liani",
				edgeType: (byte)EdgeType.GivesItem,
				sourceType: (byte)NodeType.Character)
			.AddQuest(
				"quest:meet",
				dbName: "MEET",
				implicit_: true,
				requiredItems: new[] { ("item:ring", 1) })
			.AddQuest(
				"quest:root",
				dbName: "ROOT",
				implicit_: true,
				requiredItems: new[] { ("item:eye", 1) })
			.AddUnlockPredicate("char:plax", "quest:meet")
			.Build();

		var state = new QuestStateTracker(guide);
		state.LoadState(
			currentZone: "Azure",
			activeQuests: new[] { "ROOT", "MEET" },
			completedQuests: Array.Empty<string>(),
			inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
			keyringItemKeys: Array.Empty<string>());
		var phases = new QuestPhaseTracker(guide, state);
		var frontier = new EffectiveFrontier(guide, phases);
		var registry = TestPositionResolvers.Create(guide);
		var sourceResolver = new SourceResolver(
			guide,
			phases,
			new UnlockPredicateEvaluator(guide, phases),
			new StubLivePositionProvider(),
			registry);
		var reader = ResolutionTestFactory.BuildService(
			guide,
			frontier,
			sourceResolver,
			phases,
			zoneRouter: null,
			engine: new Engine<FactKey>(),
			positionRegistry: registry,
			trackerState: new TrackerState(),
			navSet: new NavigationSet());

		var record = reader.ReadQuestResolution("quest:root", "Azure");

		Assert.NotEmpty(record.CompiledTargets);
		Assert.NotEmpty(record.NavigationTargets);
		Assert.True(guide.TryGetNodeId("char:liani", out int lianiId));
		Assert.True(guide.TryGetNodeId("quest:root", out int rootQuestNodeId));
		int rootQuestIndex = guide.FindQuestIndex(rootQuestNodeId);
		var lianiTarget = Assert.Single(
			record.CompiledTargets,
			target => target.TargetNodeId == lianiId);
		Assert.Equal(rootQuestIndex, lianiTarget.RequiredForQuestIndex);
		Assert.Equal(ResolvedTargetAvailabilityPriority.PrerequisiteFallback, lianiTarget.AvailabilityPriority);
	}

	[Fact]
	public void Read_MatchesDirectResolver_ForQuestLockedRequiredItemSources()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:eye")
			.AddItem("item:ring")
			.AddCharacter("char:plax", scene: "Stowaway", x: 10f, y: 0f, z: 20f)
			.AddCharacter("char:liani", scene: "Azure", x: 1f, y: 0f, z: 2f)
			.AddItemSource("item:eye", "char:plax", edgeType: (byte)EdgeType.DropsItem)
			.AddItemSource("item:ring", "char:liani", edgeType: (byte)EdgeType.GivesItem)
			.AddQuest("quest:meet", dbName: "MEET", implicit_: true, requiredItems: new[] { ("item:ring", 1) })
			.AddQuest("quest:root", dbName: "ROOT", implicit_: true, requiredItems: new[] { ("item:eye", 1) })
			.AddUnlockPredicate("char:plax", "quest:meet")
			.Build();
		var state = new QuestStateTracker(guide);
		state.LoadState(
			"Azure",
			new[] { "ROOT", "MEET" },
			Array.Empty<string>(),
			new Dictionary<string, int>(StringComparer.Ordinal),
			Array.Empty<string>());
		var phases = new QuestPhaseTracker(guide, state);
		var frontier = new EffectiveFrontier(guide, phases);
		var registry = TestPositionResolvers.Create(guide);
		var sourceResolver = new SourceResolver(
			guide,
			phases,
			new UnlockPredicateEvaluator(guide, phases),
			new StubLivePositionProvider(),
			registry);
		var directResolver = new QuestTargetResolver(guide, frontier, sourceResolver, zoneRouter: null);
		var reader = ResolutionTestFactory.BuildService(
			guide,
			frontier,
			sourceResolver,
			phases,
			zoneRouter: null,
			engine: new Engine<FactKey>(),
			positionRegistry: registry,
			trackerState: new TrackerState(),
			navSet: new NavigationSet());

		Assert.True(guide.TryGetNodeId("quest:root", out int rootQuestNodeId));
		int rootQuestIndex = guide.FindQuestIndex(rootQuestNodeId);
		var directTargets = directResolver.Resolve(rootQuestIndex, "Azure", session: null);
		var queryTargets = reader.ReadQuestResolution("quest:root", "Azure").CompiledTargets;

		Assert.NotEmpty(directTargets);
		Assert.Equal(
			directTargets.Select(target => guide.GetNodeKey(target.TargetNodeId)).OrderBy(key => key),
			queryTargets.Select(target => guide.GetNodeKey(target.TargetNodeId)).OrderBy(key => key));
	}

	private sealed class CompiledTargetsFixture
	{
		private CompiledTargetsFixture(
			AdventureGuide.CompiledGuide.CompiledGuide guide,
			Engine<FactKey> engine,
			CompiledTargetsQuery query,
			List<SourceResolver.ResolutionSession> usedSessions)
		{
			Guide = guide;
			Engine = engine;
			Query = query;
			UsedSessions = usedSessions;
		}

		public AdventureGuide.CompiledGuide.CompiledGuide Guide { get; }
		public Engine<FactKey> Engine { get; }
		public CompiledTargetsQuery Query { get; }
		public List<SourceResolver.ResolutionSession> UsedSessions { get; }

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
			var usedSessions = new List<SourceResolver.ResolutionSession>();

			return new CompiledTargetsFixture(
				guide,
				engine,
				new CompiledTargetsQuery(engine, guide, frontier, resolver, reader, usedSessions.Add),
				usedSessions);
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
