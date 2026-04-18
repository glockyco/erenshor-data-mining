using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

internal sealed class StubLivePositionProvider : ILivePositionProvider
{
	public WorldPosition? GetLivePosition(int spawnNodeId) => null;

	public bool IsAlive(int spawnNodeId) => false;
}

internal sealed class SelectiveLivePositionProvider : ILivePositionProvider
{
	private readonly HashSet<int> _aliveNodeIds;

	public SelectiveLivePositionProvider(IEnumerable<int> aliveNodeIds)
	{
		_aliveNodeIds = new HashSet<int>(aliveNodeIds);
	}

	public WorldPosition? GetLivePosition(int spawnNodeId) => null;

	public bool IsAlive(int spawnNodeId) => _aliveNodeIds.Contains(spawnNodeId);
}

public sealed class SourceResolverTests
{
	[Fact]
	public void Ready_to_accept_resolves_giver_position_with_giver_semantics()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:guard", scene: "Forest", x: 10f, y: 20f, z: 30f)
			.AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:guard" })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			Array.Empty<string>(),
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.ReadyToAccept, -1),
			"Forest"
		);

		guide.TryGetNodeId("char:guard", out int giverId);
		Assert.Single(targets);
		Assert.Equal(giverId, targets[0].TargetNodeId);
		Assert.Equal(giverId, targets[0].PositionNodeId);
		Assert.Equal(ResolvedTargetRole.Giver, targets[0].Role);
		Assert.Equal(QuestMarkerKind.QuestGiver, targets[0].Semantic.PreferredMarkerKind);
		Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
		Assert.Equal(10f, targets[0].X);
		Assert.Equal(20f, targets[0].Y);
		Assert.Equal(30f, targets[0].Z);
	}

	[Fact]
	public void Ready_to_accept_item_giver_without_item_resolves_acquisition_source_semantics()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:note")
			.AddCharacter("char:ghost")
			.AddSpawnPoint("spawn:ghost", scene: "Tutorial", x: 10f, y: 20f, z: 30f)
			.AddItemSource("item:note", "char:ghost", positionKeys: new[] { "spawn:ghost" })
			.AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "item:note" })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			Array.Empty<string>(),
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var targets = resolver.ResolveTargets(new FrontierEntry(0, QuestPhase.ReadyToAccept, -1), "Forest");

		guide.TryGetNodeId("char:ghost", out int sourceId);
		guide.TryGetNodeId("spawn:ghost", out int spawnId);
		var target = Assert.Single(targets);
		Assert.Equal(sourceId, target.TargetNodeId);
		Assert.Equal(spawnId, target.PositionNodeId);
		Assert.Equal(QuestMarkerKind.Objective, target.Semantic.PreferredMarkerKind);
		Assert.Equal(ResolvedActionKind.Kill, target.Semantic.ActionKind);
		Assert.Equal("Tutorial", target.Scene);
		Assert.Equal(10f, target.X);
		Assert.Equal(20f, target.Y);
		Assert.Equal(30f, target.Z);
	}

	[Fact]
	public void Accepted_with_missing_item_resolves_objective_source_semantics()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:wolf", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItem("item:pelt")
			.AddItemSource("item:pelt", "char:wolf")
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:pelt", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Forest"
		);

		guide.TryGetNodeId("char:wolf", out int wolfId);
		Assert.Single(targets);
		Assert.Equal(wolfId, targets[0].TargetNodeId);
		Assert.Equal(wolfId, targets[0].PositionNodeId);
		Assert.Equal(ResolvedTargetRole.Objective, targets[0].Role);
		Assert.Equal(QuestMarkerKind.Objective, targets[0].Semantic.PreferredMarkerKind);
		Assert.Equal(ResolvedActionKind.Kill, targets[0].Semantic.ActionKind);
		Assert.Equal(40f, targets[0].X);
		Assert.Equal(50f, targets[0].Y);
		Assert.Equal(60f, targets[0].Z);
	}

	[Fact]
	public void Accepted_with_hostile_drop_source_hides_friendly_drop_sources()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:wolf", scene: "Forest", x: 40f, y: 50f, z: 60f, isFriendly: false)
			.AddCharacter("char:ranger", scene: "Forest", x: 70f, y: 80f, z: 90f, isFriendly: true)
			.AddItem("item:pelt")
			.AddItemSource("item:pelt", "char:wolf", edgeType: (byte)EdgeType.DropsItem)
			.AddItemSource("item:pelt", "char:ranger", edgeType: (byte)EdgeType.DropsItem)
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:pelt", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Forest"
		);

		Assert.Single(targets);
		guide.TryGetNodeId("char:wolf", out int wolfId);
		Assert.Equal(wolfId, targets[0].TargetNodeId);
	}

	[Fact]
	public void Accepted_with_satisfied_items_resolves_turnin_semantics()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:pelt")
			.AddCharacter("char:turnin", scene: "Forest", x: 70f, y: 80f, z: 90f)
			.AddQuest(
				"quest:a",
				dbName: "QUESTA",
				completers: new[] { "char:turnin" },
				requiredItems: new[] { ("item:pelt", 1) }
			)
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int> { ["item:pelt"] = 1 },
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Forest"
		);

		guide.TryGetNodeId("char:turnin", out int turnInId);
		Assert.Single(targets);
		Assert.Equal(turnInId, targets[0].TargetNodeId);
		Assert.Equal(ResolvedTargetRole.TurnIn, targets[0].Role);
		Assert.Equal(QuestMarkerKind.TurnInReady, targets[0].Semantic.PreferredMarkerKind);
		Assert.Equal(ResolvedActionKind.Give, targets[0].Semantic.ActionKind);
	}

	[Fact]
	public void Accepted_with_unindexed_required_item_does_not_emit_turnin()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:turnin", scene: "Forest", x: 70f, y: 80f, z: 90f)
			.AddQuest(
				"quest:a",
				dbName: "QUESTA",
				completers: new[] { "char:turnin" },
				requiredItems: new[] { ("item:mystery", 1) }
			)
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Forest"
		);

		Assert.Empty(targets);
	}

	[Fact]
	public void Accepted_with_mined_mining_source_positions_uses_position_resolver_actionability()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:coal")
			.AddMiningNode("mine:mined", scene: "Azure", x: 5f, y: 0f, z: 0f)
			.AddItemSource(
				"item:coal",
				"mine:mined",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.MiningNode
			)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:coal", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		Assert.True(guide.TryGetNodeId("mine:mined", out int minedId));
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new SelectiveLivePositionProvider(new[] { minedId }),
			TestPositionResolvers.Create(
				guide,
				new Dictionary<string, bool> { ["mine:mined"] = false }
			)
		);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(0, QuestPhase.Accepted, -1),
			"Azure"
		);

		var target = Assert.Single(targets);
		Assert.Equal(minedId, target.TargetNodeId);
		Assert.Equal(minedId, target.PositionNodeId);
		Assert.Equal(ResolvedActionKind.Mine, target.Semantic.ActionKind);
		Assert.False(target.IsActionable);
	}

	[Fact]
	public void Accepted_with_recipe_source_resolves_material_source_targets()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:ore")
			.AddCharacter("char:wolf", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:ore", "char:wolf")
			.AddItem("item:key")
			.AddRecipe("recipe:key")
			.AddItemSource(
				"item:key",
				"recipe:key",
				edgeType: (byte)EdgeType.Produces,
				sourceType: (byte)NodeType.Recipe
			)
			.AddEdge("recipe:key", "item:ore", EdgeType.RequiresMaterial, quantity: 1)
			.AddEdge("recipe:key", "item:key", EdgeType.Produces)
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:key", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);
		Assert.True(guide.TryGetNodeId("quest:a", out int questNodeId));
		int questIndex = guide.FindQuestIndex(questNodeId);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(questIndex, QuestPhase.Accepted, -1),
			"Forest"
		);

		guide.TryGetNodeId("char:wolf", out int wolfId);
		Assert.Single(targets);
		Assert.Equal(wolfId, targets[0].TargetNodeId);
		Assert.Equal(ResolvedActionKind.Kill, targets[0].Semantic.ActionKind);
	}

	[Fact]
	public void Accepted_with_reward_quest_source_resolves_reward_quest_frontier()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:note")
			.AddCharacter("char:percy", scene: "Beach", x: 10f, y: 20f, z: 30f)
			.AddQuest("quest:percy", dbName: "PERCY", givers: new[] { "char:percy" })
			.AddEdge("quest:percy", "item:note", EdgeType.RewardsItem)
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:note", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);
		Assert.True(guide.TryGetNodeId("quest:a", out int questNodeId));
		int questIndex = guide.FindQuestIndex(questNodeId);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(questIndex, QuestPhase.Accepted, -1),
			"Beach"
		);

		guide.TryGetNodeId("char:percy", out int percyId);
		Assert.Single(targets);
		Assert.Equal(percyId, targets[0].TargetNodeId);
		Assert.Equal(ResolvedTargetRole.Giver, targets[0].Role);
		Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
	}

	[Fact]
	public void Accepted_with_blocked_source_resolves_unlock_quest_frontier()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:crystal")
			.AddCharacter("char:keeper", scene: "Vault", x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:crystal", "char:keeper")
			.AddCharacter("char:elder", scene: "Town", x: 5f, y: 6f, z: 7f)
			.AddQuest("quest:gate", dbName: "GATE", givers: new[] { "char:elder" })
			.AddUnlockPredicate("char:keeper", "quest:gate")
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:crystal", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);
		Assert.True(guide.TryGetNodeId("quest:a", out int questNodeId));
		int questIndex = guide.FindQuestIndex(questNodeId);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(questIndex, QuestPhase.Accepted, -1),
			"Town"
		);

		guide.TryGetNodeId("char:elder", out int elderId);
		Assert.Single(targets);
		Assert.Equal(elderId, targets[0].TargetNodeId);
		Assert.Equal(ResolvedTargetRole.Giver, targets[0].Role);
		Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
	}

	[Fact]
	public void Accepted_read_step_without_item_resolves_acquisition_source_semantics()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:note")
			.AddCharacter("char:ghost", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:note", "char:ghost")
			.AddQuest("quest:a", dbName: "QUESTA")
			.AddStep("quest:a", StepLabels.Read, "item:note")
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var targets = resolver.ResolveTargets(new FrontierEntry(0, QuestPhase.Accepted, -1), "Forest");

		guide.TryGetNodeId("char:ghost", out int ghostId);
		var target = Assert.Single(targets);
		Assert.Equal(ghostId, target.TargetNodeId);
		Assert.Equal(NavigationGoalKind.ReadItem, target.Semantic.GoalKind);
		Assert.Equal(QuestMarkerKind.Objective, target.Semantic.PreferredMarkerKind);
		Assert.Equal(ResolvedActionKind.Kill, target.Semantic.ActionKind);
	}

	[Fact]
	public void Accepted_with_mixed_direct_and_blocked_sources_prefers_direct_targets_over_fallbacks()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:spice")
			.AddCharacter("char:elder", scene: "Forest", x: 5f, y: 6f, z: 7f)
			.AddQuest("quest:key", dbName: "KEY", givers: new[] { "char:elder" })
			.AddCharacter("char:crypt", scene: "Vault", x: 10f, y: 20f, z: 30f)
			.AddItemSource("item:spice", "char:crypt")
			.AddUnlockPredicate("char:crypt", "quest:key")
			.AddCharacter("char:plax", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:spice", "char:plax")
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:spice", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var resolver = new SourceResolver(
			guide,
			tracker,
			new UnlockPredicateEvaluator(guide, tracker),
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);
		Assert.True(guide.TryGetNodeId("quest:root", out int questNodeId));
		int questIndex = guide.FindQuestIndex(questNodeId);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(questIndex, QuestPhase.Accepted, -1),
			"Forest"
		);

		Assert.Equal(2, targets.Count);
		Assert.Equal("char:plax", guide.GetNodeKey(targets[0].TargetNodeId));
		Assert.Equal(ResolvedTargetRole.Objective, targets[0].Role);
		Assert.Equal("char:elder", guide.GetNodeKey(targets[1].TargetNodeId));
		Assert.Equal(ResolvedTargetRole.Giver, targets[1].Role);
	}

	[Fact]
	public void ResolvedTarget_exposes_availability_priority_for_mixed_sources()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:spice")
			.AddCharacter("char:elder", scene: "Forest", x: 5f, y: 6f, z: 7f)
			.AddQuest("quest:key", dbName: "KEY", givers: new[] { "char:elder" })
			.AddCharacter("char:crypt", scene: "Vault", x: 10f, y: 20f, z: 30f)
			.AddItemSource("item:spice", "char:crypt")
			.AddUnlockPredicate("char:crypt", "quest:key")
			.AddCharacter("char:plax", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:spice", "char:plax")
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:spice", 1) })
			.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var resolver = new SourceResolver(
			guide,
			tracker,
			new UnlockPredicateEvaluator(guide, tracker),
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);
		Assert.True(guide.TryGetNodeId("quest:root", out int questNodeId));
		int questIndex = guide.FindQuestIndex(questNodeId);

		var targets = resolver.ResolveTargets(
			new FrontierEntry(questIndex, QuestPhase.Accepted, -1),
			"Forest"
		);
		var availabilityPriority = typeof(ResolvedTarget).GetProperty("AvailabilityPriority");

		Assert.NotNull(availabilityPriority);
		Assert.Equal("Immediate", availabilityPriority!.GetValue(targets[0])?.ToString());
		Assert.Equal("PrerequisiteFallback", availabilityPriority.GetValue(targets[1])?.ToString());
	}

	[Fact]
	public void Accepted_with_shared_reward_subtrees_memoizes_quest_frontiers()
	{
		const int depth = 20;
		var builder = new CompiledGuideBuilder()
			.AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:0", 1) });

		for (int i = 0; i <= depth; i++)
			builder.AddItem($"item:{i}");

		var activeQuests = new List<string> { "ROOT" };
		for (int i = 0; i < depth; i++)
		{
			string qa = $"Q{i}A";
			string qb = $"Q{i}B";
			activeQuests.Add(qa);
			activeQuests.Add(qb);
			builder
				.AddQuest(
					$"quest:{i}:a",
					dbName: qa,
					requiredItems: new[] { ($"item:{i + 1}", 1) },
					chainsTo: i == depth - 1 ? Array.Empty<string>() : new[] { $"quest:{i + 1}:a", $"quest:{i + 1}:b" }
				)
				.AddQuest(
					$"quest:{i}:b",
					dbName: qb,
					requiredItems: new[] { ($"item:{i + 1}", 1) },
					chainsTo: i == depth - 1 ? Array.Empty<string>() : new[] { $"quest:{i + 1}:a", $"quest:{i + 1}:b" }
				)
				.AddEdge($"quest:{i}:a", $"item:{i}", EdgeType.RewardsItem)
				.AddEdge($"quest:{i}:b", $"item:{i}", EdgeType.RewardsItem);
		}

		builder.AddItemSource(
			$"item:{depth}",
			"char:leaf",
			edgeType: (byte)EdgeType.DropsItem,
			sourceType: (byte)NodeType.Character
		);

		var guide = builder.Build();
		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			activeQuests,
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var resolver = new SourceResolver(
			guide,
			tracker,
			new UnlockPredicateEvaluator(guide, tracker),
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);
		Assert.True(guide.TryGetNodeId("quest:root", out int questNodeId));
		int questIndex = guide.FindQuestIndex(questNodeId);

		// Structural regression guard against combinatorial blow-up in
		// shared-reward subtree resolution. Without caching, the paired
		// quest-chain structure would visit Q(i)A and Q(i)B exponentially many
		// times through the reward dependency graph (2^depth traversals). With
		// the session cache, each quest's frontier resolves at most once, so the
		// tracer's OnFrontierEntry count is bounded by total quest count
		// (2*depth + 1 = 41 here).
		var tracer = new CountingResolutionTracer();
		var targets = resolver.ResolveTargets(
			new FrontierEntry(questIndex, QuestPhase.Accepted, -1),
			"Town",
			tracer
		);

		Assert.NotEmpty(targets);
		Assert.True(
			tracer.FrontierEntryCount < 500,
			$"FrontierEntryCount={tracer.FrontierEntryCount}; combinatorial blow-up suspected (expected O(depth), not O(2^depth))."
		);
	}
}
