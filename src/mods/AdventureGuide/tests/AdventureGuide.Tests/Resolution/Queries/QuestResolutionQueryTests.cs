using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Frontier;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Resolution.Queries;

public sealed class QuestResolutionQueryTests
{
	[Fact]
	public void Compute_ComposesFrontierTargetsAndBlocking_ForQuestAndScene()
	{
		var fixture = QuestResolutionQueryFixture.Create();

		var record = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Same(fixture.CompiledResult.Frontier, record.Frontier);
		Assert.Same(fixture.CompiledResult.Targets, record.CompiledTargets);
		Assert.True(record.TryGetBlockingZoneLineNodeId("Forest", out int zoneLineNodeId));
		Assert.Equal(77, zoneLineNodeId);
		Assert.Same(fixture.NavigationTargets, record.NavigationTargets);
		Assert.Equal(1, fixture.ProjectCount);
	}

	[Fact]
	public void ReadTwice_Memoises()
	{
		var fixture = QuestResolutionQueryFixture.Create();

		var first = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));
		var second = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Same(first, second);
		Assert.Equal(1, fixture.ComposedComputeCount);
		Assert.Equal(1, fixture.CompiledComputeCount);
		Assert.Equal(1, fixture.BlockingComputeCount);
	}

	[Fact]
	public void InvalidatingQuestActive_RecomputesCompiledTargets_ButNotBlockingZones()
	{
		var fixture = QuestResolutionQueryFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		fixture.CompiledResult = fixture.CreateCompiledResult(targetNodeId: fixture.Guide.QuestNodeId(0));
		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "quest:root") });
		var second = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.NotSame(first, second);
		Assert.Equal(2, fixture.ComposedComputeCount);
		Assert.Equal(2, fixture.CompiledComputeCount);
		Assert.Equal(1, fixture.BlockingComputeCount);
	}

	[Fact]
	public void InvalidatingSourceState_RecomputesBlockingZones_ButNotCompiledTargets()
	{
		var fixture = QuestResolutionQueryFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		fixture.BlockingResult = new BlockingZonesResult(
			new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase) { ["Forest"] = 88 });
		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.SourceState, "*") });
		var second = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.NotSame(first, second);
		Assert.Equal(2, fixture.ComposedComputeCount);
		Assert.Equal(1, fixture.CompiledComputeCount);
		Assert.Equal(2, fixture.BlockingComputeCount);
	}

	[Fact]
	public void BackdatingSubQuery_SuppressesComposedRecompute()
	{
		var fixture = QuestResolutionQueryFixture.Create();
		var first = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		fixture.Engine.InvalidateFacts(new[] { new FactKey(FactKind.QuestActive, "quest:root") });
		var second = fixture.Engine.Read(fixture.Query.Query, ("quest:root", "Town"));

		Assert.Same(first, second);
		Assert.Equal(1, fixture.ComposedComputeCount);
		Assert.Equal(2, fixture.CompiledComputeCount);
		Assert.Equal(1, fixture.BlockingComputeCount);
	}

	private sealed class QuestResolutionQueryFixture
	{
		private readonly IReadOnlyList<FrontierEntry> _frontier;
		private readonly IReadOnlyList<ResolvedTarget> _compiledTargets;

		private QuestResolutionQueryFixture(
			CompiledGuideModel guide,
			Engine<FactKey> engine,
			QuestResolutionQuery query,
			IReadOnlyList<FrontierEntry> frontier,
			IReadOnlyList<ResolvedTarget> compiledTargets,
			IReadOnlyList<ResolvedQuestTarget> navigationTargets)
		{
			Guide = guide;
			Engine = engine;
			Query = query;
			_navigationTargets = navigationTargets;
			_frontier = frontier;
			_compiledTargets = compiledTargets;
			CompiledResult = new CompiledTargetsResult(frontier, compiledTargets);
			BlockingResult = new BlockingZonesResult(
				new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase) { ["Forest"] = 77 });
		}

		private readonly IReadOnlyList<ResolvedQuestTarget> _navigationTargets;

		public CompiledGuideModel Guide { get; }
		public Engine<FactKey> Engine { get; }
		public QuestResolutionQuery Query { get; }
		public CompiledTargetsResult CompiledResult { get; set; }
		public BlockingZonesResult BlockingResult { get; set; }
		public IReadOnlyList<ResolvedQuestTarget> NavigationTargets => _navigationTargets;
		public int ComposedComputeCount { get; private set; }
		public int CompiledComputeCount { get; private set; }
		public int BlockingComputeCount { get; private set; }
		public int ProjectCount { get; private set; }

		public static QuestResolutionQueryFixture Create()
		{
			var guide = new CompiledGuideBuilder()
				.AddQuest("quest:root", dbName: "ROOT")
				.AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
				.Build();
			var engine = new Engine<FactKey>();
			var frontier = Array.Empty<FrontierEntry>();
			var semantic = new ResolvedActionSemantic(
				NavigationGoalKind.Generic,
				NavigationTargetKind.Character,
				ResolvedActionKind.Talk,
				goalNodeKey: null,
				goalQuantity: null,
				keywordText: null,
				payloadText: null,
				targetIdentityText: "Leaf",
				contextText: null,
				rationaleText: null,
				zoneText: "Town",
				availabilityText: null,
				preferredMarkerKind: QuestMarkerKind.Objective,
				markerPriority: 0);
			var targetNode = guide.GetNode("char:leaf")!;
			var nodeContext = new ResolvedNodeContext("char:leaf", targetNode);
			var explanation = new NavigationExplanation(
				NavigationGoalKind.Generic,
				NavigationTargetKind.Character,
				nodeContext,
				nodeContext,
				primaryText: "Talk to Leaf",
				targetIdentityText: "Leaf",
				zoneText: "Town",
				secondaryText: null,
				tertiaryText: null);
			guide.TryGetNodeId("char:leaf", out int leafNodeId);
			var compiledTargets = new[]
			{
				new ResolvedTarget(
					targetNodeId: leafNodeId,
					positionNodeId: leafNodeId,
					role: ResolvedTargetRole.Objective,
					semantic: semantic,
					x: 1f,
					y: 2f,
					z: 3f,
					scene: "Town",
					isLive: false,
					isActionable: true,
					questIndex: 0,
					requiredForQuestIndex: -1)
			};
			var navigationTargets = new[]
			{
				new ResolvedQuestTarget(
					targetNodeKey: "char:leaf",
					scene: "Town",
					sourceKey: "char:leaf",
					goalNode: nodeContext,
					targetNode: nodeContext,
					semantic: semantic,
					explanation: explanation,
					x: 1f,
					y: 2f,
					z: 3f)
			};

			QuestResolutionQueryFixture? fixture = null;
			var compiledQuery = engine.DefineQuery<(string QuestKey, string Scene), CompiledTargetsResult>(
				"CompiledTargetsStub",
				(ctx, key) =>
				{
					fixture!.CompiledComputeCount++;
					ctx.RecordFact(new FactKey(FactKind.QuestActive, key.QuestKey));
					return fixture.CompiledResult;
				});
			var blockingQuery = engine.DefineQuery<string, BlockingZonesResult>(
				"BlockingZonesStub",
				(ctx, scene) =>
				{
					fixture!.BlockingComputeCount++;
					ctx.RecordFact(new FactKey(FactKind.SourceState, "*"));
					return fixture.BlockingResult;
				});
			var query = new QuestResolutionQuery(
				engine,
				compiledQuery,
				blockingQuery,
				(targets, scene) =>
				{
					fixture!.ProjectCount++;
					Assert.Same(fixture.CompiledResult.Targets, targets);
					Assert.Equal("Town", scene);
					return fixture.NavigationTargets;
				},
				() => fixture!.ComposedComputeCount++);
			fixture = new QuestResolutionQueryFixture(
				guide,
				engine,
				query,
				frontier,
				compiledTargets,
				navigationTargets);
			return fixture;
		}

		public CompiledTargetsResult CreateCompiledResult(int targetNodeId) =>
			new(_frontier, new[]
			{
				new ResolvedTarget(
					targetNodeId: targetNodeId,
					positionNodeId: targetNodeId,
					role: ResolvedTargetRole.Objective,
					semantic: _compiledTargets[0].Semantic,
					x: _compiledTargets[0].X,
					y: _compiledTargets[0].Y,
					z: _compiledTargets[0].Z,
					scene: _compiledTargets[0].Scene,
					isLive: _compiledTargets[0].IsLive,
					isActionable: _compiledTargets[0].IsActionable,
					questIndex: _compiledTargets[0].QuestIndex,
					requiredForQuestIndex: _compiledTargets[0].RequiredForQuestIndex,
					availabilityPriority: _compiledTargets[0].AvailabilityPriority)
			});
	}
}
