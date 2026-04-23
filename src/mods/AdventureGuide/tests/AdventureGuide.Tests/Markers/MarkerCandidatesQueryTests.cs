using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Markers;
using AdventureGuide.Markers.Queries;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Frontier;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Markers;

public sealed class MarkerCandidatesQueryTests
{
	[Fact]
	public void Read_EmitsCandidate_ForActiveQuestWithOneTarget()
	{
		var fixture = MarkerCandidatesFixture.CreateActiveQuest();

		var list = fixture.Engine.Read(fixture.Query.Query, "Town");

		var active = Assert.Single(list.Candidates);
		Assert.Equal("quest:a", active.QuestKey);
		Assert.Equal("char:leaf", active.TargetNodeKey);
		Assert.Equal("spawn:leaf-1", active.PositionNodeKey);
		Assert.Equal(SpawnCategory.Alive, active.SpawnCategory);
	}

	[Fact]
	public void Read_DoesNotEmitRespawnTimerSibling_ForSpawnBackedTarget()
	{
		var fixture = MarkerCandidatesFixture.CreateActiveQuest();

		var list = fixture.Engine.Read(fixture.Query.Query, "Town");

		var candidate = Assert.Single(list.Candidates);
		Assert.Equal("quest:a", candidate.QuestKey);
		Assert.Equal("char:leaf", candidate.TargetNodeKey);
		Assert.Equal("spawn:leaf-1", candidate.PositionNodeKey);
		Assert.Equal("spawn:leaf-1", candidate.SourceNodeKey);
		Assert.Equal(QuestMarkerKind.Objective, candidate.QuestKind);
		Assert.Equal(SpawnCategory.Alive, candidate.SpawnCategory);
	}

	[Fact]
	public void Read_Memoises_WhenNoInvalidationOccurs()
	{
		var fixture = MarkerCandidatesFixture.CreateActiveQuest();

		var first = fixture.Engine.Read(fixture.Query.Query, "Town");
		var second = fixture.Engine.Read(fixture.Query.Query, "Town");

		Assert.Same(first, second);
	}

	[Fact]
	public void Read_DoesNotRecompute_WhenUnreadFactInvalidates()
	{
		var fixture = MarkerCandidatesFixture.CreateActiveQuest();

		fixture.Engine.Read(fixture.Query.Query, "Town");
		int countBefore = fixture.SubQueryComputeCount;

		// TimeOfDay is never read by the query; invalidation must not cascade.
		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.TimeOfDay, "current") });
		fixture.Engine.Read(fixture.Query.Query, "Town");

		Assert.Equal(countBefore, fixture.SubQueryComputeCount);
	}

	[Fact]
	public void Read_Recomputes_WhenSourceStateInvalidates_AndReflectsNewCategory()
	{
		var fixture = MarkerCandidatesFixture.CreateActiveQuest();

		var first = fixture.Engine.Read(fixture.Query.Query, "Town");
		Assert.Equal(SpawnCategory.Alive, first.Candidates[0].SpawnCategory);

		fixture.SourceStates["spawn:leaf-1"] = SpawnCategory.Dead;
		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "spawn:leaf-1") });
		var second = fixture.Engine.Read(fixture.Query.Query, "Town");

		Assert.NotSame(first, second);
		Assert.All(second.Candidates, c => Assert.Equal(SpawnCategory.Dead, c.SpawnCategory));
	}

	[Fact]
	public void Read_Backdates_ThroughSubQuery_WhenQuestResolutionResultUnchanged()
	{
		var fixture = MarkerCandidatesFixture.CreateActiveQuest();

		var first = fixture.Engine.Read(fixture.Query.Query, "Town");
		int countBefore = fixture.QuestResolutionComputeCount;

		// Per-quest QuestActive fact is recorded by the QuestResolution sub-query
		// stub but not directly by the parent. Invalidating it forces the sub-query
		// to recompute; because the stub returns the same QuestResolutionRecord
		// instance, value-equality backdating preserves its revision and the
		// parent (MarkerCandidates) entry stays fresh — same reference returned.
		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "quest:a") });
		var second = fixture.Engine.Read(fixture.Query.Query, "Town");

		Assert.True(fixture.QuestResolutionComputeCount > countBefore);
		Assert.Same(first, second);
	}

	[Fact]
	public void Read_SuppressesBlockedCandidate_WhenNonBlockedShareSamePosition()
	{
		var fixture = MarkerCandidatesFixture.CreateBlockedOverlap();

		var list = fixture.Engine.Read(fixture.Query.Query, "Town");

		var candidate = Assert.Single(list.Candidates);
		Assert.Equal("quest:a", candidate.QuestKey);
		Assert.NotEqual(QuestMarkerKind.QuestGiverBlocked, candidate.QuestKind);
	}

	private sealed class MarkerCandidatesFixture
	{
		public Engine<FactKey> Engine { get; }
		public MarkerCandidatesQuery Query { get; }
		public Dictionary<string, SpawnCategory> SourceStates { get; }
		public int SubQueryComputeCount { get; private set; }
		public int QuestResolutionComputeCount { get; private set; }

		private MarkerCandidatesFixture(
			Engine<FactKey> engine,
			MarkerCandidatesQuery query,
			Dictionary<string, SpawnCategory> sourceStates)
		{
			Engine = engine;
			Query = query;
			SourceStates = sourceStates;
		}

		public void BumpSubQueryComputeCount() => SubQueryComputeCount++;
		public void BumpQuestResolutionComputeCount() => QuestResolutionComputeCount++;

		public static MarkerCandidatesFixture CreateActiveQuest()
		{
			var guide = new CompiledGuideBuilder()
				.AddQuest("quest:a", dbName: "QUESTA")
				.AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
				.AddSpawnPoint("spawn:leaf-1", scene: "Town", x: 1f, y: 2f, z: 3f)
				.Build();

			var engine = new Engine<FactKey>();
			var sourceStates = new Dictionary<string, SpawnCategory>(StringComparer.Ordinal)
			{
				["spawn:leaf-1"] = SpawnCategory.Alive,
				["char:leaf"] = SpawnCategory.Alive,
			};

			var reader = new GuideReader(
				engine,
				new FakeInventory(),
				new FakeQuestState(
					currentScene: "Town",
					actionable: new[] { "QUESTA" },
					implicitAvail: Array.Empty<string>(),
					completed: Array.Empty<string>()),
				new FakeTrackerState(Array.Empty<string>()),
				new FakeNavigationSet(Array.Empty<string>()),
				new FakeSourceState(sourceStates));

			guide.TryGetNodeId("char:leaf", out int leafNodeId);
			guide.TryGetNodeId("spawn:leaf-1", out int spawnNodeId);

			var semantic = new ResolvedActionSemantic(
				NavigationGoalKind.Generic,
				NavigationTargetKind.Character,
				ResolvedActionKind.Talk,
				goalNodeKey: null,
				goalQuantity: null,
				keywordText: null,
				payloadText: null,
				targetIdentityText: "char:leaf",
				contextText: null,
				rationaleText: null,
				zoneText: "Town",
				availabilityText: null,
				preferredMarkerKind: QuestMarkerKind.Objective,
				markerPriority: 0);

			var resolvedTarget = new ResolvedTarget(
				targetNodeId: leafNodeId,
				positionNodeId: spawnNodeId,
				role: ResolvedTargetRole.Objective,
				semantic: semantic,
				x: 1f,
				y: 2f,
				z: 3f,
				scene: "Town",
				isLive: false,
				isActionable: true,
				questIndex: 0,
				requiredForQuestIndex: -1);

			

			MarkerCandidatesFixture? fixture = null;
			var navigableQuery = engine.DefineQuery<Unit, NavigableQuestSet>(
				"NavigableQuestsStub",
				(ctx, _) =>
				{
					fixture!.BumpSubQueryComputeCount();
					ctx.RecordFact(new FactKey(FactKind.NavSet, "*"));
					ctx.RecordFact(new FactKey(FactKind.TrackerSet, "*"));
					ctx.RecordFact(new FactKey(FactKind.QuestActive, "*"));
					return new NavigableQuestSet(new[] { "quest:a" });				});

			var resolutionRecord = new QuestResolutionRecord(
				questKey: "quest:a",
				currentScene: "Town",
				frontier: Array.Empty<FrontierEntry>(),
				compiledTargets: new[] { resolvedTarget },
				navigationTargetsFactory: () => Array.Empty<ResolvedQuestTarget>(),
				blockingZoneLineByScene: new Dictionary<string, int>());
			var questResolutionQuery = engine.DefineQuery<(string, string), QuestResolutionRecord>(
				"QuestResolutionStub",
				(ctx, key) =>
				{
					fixture!.BumpQuestResolutionComputeCount();
					ctx.RecordFact(new FactKey(FactKind.QuestActive, key.Item1));
					return resolutionRecord;
				});

			var query = new MarkerCandidatesQuery(
				engine,
				guide,
				reader,
				navigableQuery,
				questResolutionQuery);

			fixture = new MarkerCandidatesFixture(engine, query, sourceStates);
			return fixture;
		}

		public static MarkerCandidatesFixture CreateBlockedOverlap()
		{
			var guide = new CompiledGuideBuilder()
				.AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:guard" })
				.AddQuest(
					"quest:b",
					dbName: "QUESTB",
					givers: new[] { "char:guard" },
					prereqs: new[] { "quest:c" })
				.AddQuest("quest:c", dbName: "QUESTC")
				.AddCharacter("char:guard", scene: "Town", x: 3f, y: 0f, z: 0f)
				.Build();

			var engine = new Engine<FactKey>();
			var sourceStates = new Dictionary<string, SpawnCategory>(StringComparer.Ordinal)
			{
				["char:guard"] = SpawnCategory.Alive,
			};

			var reader = new GuideReader(
				engine,
				new FakeInventory(),
				new FakeQuestState(
					currentScene: "Town",
					actionable: Array.Empty<string>(),
					implicitAvail: Array.Empty<string>(),
					completed: Array.Empty<string>()),
				new FakeTrackerState(Array.Empty<string>()),
				new FakeNavigationSet(Array.Empty<string>()),
				new FakeSourceState(sourceStates));

			var navigableQuery = engine.DefineQuery<Unit, NavigableQuestSet>(
				"NavigableQuestsStub",
				(_, _) => new NavigableQuestSet(Array.Empty<string>()));
			var questResolutionQuery = engine.DefineQuery<(string, string), QuestResolutionRecord>(
				"QuestResolutionStub",
				(_, _) => throw new InvalidOperationException("QuestResolution should not run for giver-only overlap"));
			var query = new MarkerCandidatesQuery(
				engine,
				guide,
				reader,
				navigableQuery,
				questResolutionQuery);

			return new MarkerCandidatesFixture(engine, query, sourceStates);
		}
	}

	private sealed class FakeInventory : IInventoryFactSource
	{
		public int GetCount(string itemId) => 0;
	}

	private sealed class FakeQuestState : IQuestStateFactSource
	{
		private readonly HashSet<string> _actionable;
		private readonly HashSet<string> _implicitAvail;
		private readonly HashSet<string> _completed;

		public FakeQuestState(
			string currentScene,
			IEnumerable<string> actionable,
			IEnumerable<string> implicitAvail,
			IEnumerable<string> completed)
		{
			CurrentScene = currentScene;
			_actionable = new HashSet<string>(actionable, StringComparer.OrdinalIgnoreCase);
			_implicitAvail = new HashSet<string>(implicitAvail, StringComparer.OrdinalIgnoreCase);
			_completed = new HashSet<string>(completed, StringComparer.OrdinalIgnoreCase);
		}

		public string CurrentScene { get; }
		public bool IsActive(string dbName) => _actionable.Contains(dbName);
		public bool IsCompleted(string dbName) => _completed.Contains(dbName);
		public IEnumerable<string> GetActionableQuestDbNames() => _actionable;
		public IEnumerable<string> GetImplicitlyAvailableQuestDbNames() => _implicitAvail;
	}

	private sealed class FakeTrackerState : ITrackerStateFactSource
	{
		public FakeTrackerState(IReadOnlyList<string> trackedQuests) => TrackedQuests = trackedQuests;
		public IReadOnlyList<string> TrackedQuests { get; }
	}

	private sealed class FakeNavigationSet : INavigationSetFactSource
	{
		public FakeNavigationSet(IReadOnlyCollection<string> keys) => Keys = keys;
		public IReadOnlyCollection<string> Keys { get; }
	}

	private sealed class FakeSourceState : ISourceStateFactSource
	{
		private readonly Dictionary<string, SpawnCategory> _states;

		public FakeSourceState(Dictionary<string, SpawnCategory> states) => _states = states;

		public SpawnCategory GetCategory(Node node) =>
			_states.TryGetValue(node.Key, out var cat) ? cat : SpawnCategory.NotApplicable;
	}
}
