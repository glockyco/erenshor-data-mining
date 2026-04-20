using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Markers;
using AdventureGuide.Markers.Queries;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Markers;

public sealed class MarkerProjectorTests
{
	[Fact]
	public void Project_RebindsLiveRefs_WhenInvalidationRunsDespiteReusedCandidateList()
	{
		var fixture = MarkerProjectorFixture.CreateActiveQuest();

		fixture.Projector.Project();
		int initialSpawnCalls = fixture.LiveState.SpawnCallCount("spawn:leaf-1");
		Assert.True(initialSpawnCalls > 0,
			"First projection must bind the spawn-backed entry.");

		fixture.Projector.Project();
		Assert.Equal(initialSpawnCalls, fixture.LiveState.SpawnCallCount("spawn:leaf-1"));

		fixture.Projector.InvalidateProjection();
		fixture.Projector.Project();

		Assert.Equal(initialSpawnCalls * 2, fixture.LiveState.SpawnCallCount("spawn:leaf-1"));
	}

	private sealed class MarkerProjectorFixture
	{
		private MarkerProjectorFixture(
			MarkerProjector projector,
			FakeMarkerLiveStateProvider liveState)
		{
			Projector = projector;
			LiveState = liveState;
		}

		public MarkerProjector Projector { get; }
		public FakeMarkerLiveStateProvider LiveState { get; }

		public static MarkerProjectorFixture CreateActiveQuest()
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

			var navigable = new NavigableQuestSet(new[] { "quest:a" });
			var navigableQuery = engine.DefineQuery<Unit, NavigableQuestSet>(
				"NavigableQuestsStub",
				(ctx, _) =>
				{
					ctx.RecordFact(new FactKey(FactKind.NavSet, "*"));
					ctx.RecordFact(new FactKey(FactKind.TrackerSet, "*"));
					ctx.RecordFact(new FactKey(FactKind.QuestActive, "*"));
					return navigable;
				});

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
					ctx.RecordFact(new FactKey(FactKind.QuestActive, key.Item1));
					return resolutionRecord;
				});

			var query = new MarkerCandidatesQuery(
				engine,
				guide,
				reader,
				navigableQuery,
				questResolutionQuery);
			reader.SetMarkerCandidatesQuery(query);

			var liveState = new FakeMarkerLiveStateProvider();
			var projector = new MarkerProjector(reader, liveState, guide);
			return new MarkerProjectorFixture(projector, liveState);
		}
	}

	private sealed class FakeMarkerLiveStateProvider : IMarkerLiveStateProvider
	{
		private readonly Dictionary<string, int> _spawnCalls = new(StringComparer.Ordinal);
		private readonly Dictionary<string, int> _characterCalls = new(StringComparer.Ordinal);
		private readonly Dictionary<string, int> _miningCalls = new(StringComparer.Ordinal);
		private readonly Dictionary<string, int> _itemBagCalls = new(StringComparer.Ordinal);

		public int SpawnCallCount(string nodeKey) =>
			_spawnCalls.TryGetValue(nodeKey, out var count) ? count : 0;

		public SpawnInfo GetSpawnState(Node spawnNode)
		{
			_spawnCalls[spawnNode.Key] = SpawnCallCount(spawnNode.Key) + 1;
			return default;
		}

		public SpawnInfo GetCharacterState(Node characterNode)
		{
			_characterCalls[characterNode.Key] = (_characterCalls.TryGetValue(characterNode.Key, out var c) ? c : 0) + 1;
			return default;
		}

		public MiningInfo GetMiningState(Node miningNode)
		{
			_miningCalls[miningNode.Key] = (_miningCalls.TryGetValue(miningNode.Key, out var c) ? c : 0) + 1;
			return default;
		}

		public NodeState GetItemBagState(Node itemBagNode)
		{
			_itemBagCalls[itemBagNode.Key] = (_itemBagCalls.TryGetValue(itemBagNode.Key, out var c) ? c : 0) + 1;
			return NodeState.Unknown;
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
