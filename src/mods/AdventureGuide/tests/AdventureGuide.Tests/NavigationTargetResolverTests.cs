using AdventureGuide.Diagnostics;
using AdventureGuide.Incremental;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Frontier;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests;

public sealed class NavigationTargetResolverTests
{
	[Fact]
	public void Resolve_QuestKey_UsesCompiledFrontierTargets()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:giver", scene: "Forest", x: 10f, y: 20f, z: 30f)
			.AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "char:giver" })
			.Build();
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			Array.Empty<string>(),
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var positionRegistry = CreatePositionRegistry(guide);
		var sourceResolver = new SourceResolver(
			guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry
		);
		var targetResolver = new NavigationTargetResolver(
			guide,
			ResolutionTestFactory.BuildService(
				guide,
				frontier,
				sourceResolver,
				zoneRouter: null,
				positionRegistry: positionRegistry
			),
			null,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, null)
		);

		var targets = targetResolver.Resolve("quest:a", "Forest");

		Assert.Single(targets);
		Assert.Equal("char:giver", targets[0].TargetNodeKey);
		Assert.Equal("char:giver", targets[0].SourceKey);
		Assert.Equal("quest:a", targets[0].GoalNode.Node.DisplayName);
		Assert.Equal("char:giver", targets[0].TargetNode.Node.DisplayName);
		Assert.Equal(QuestMarkerKind.QuestGiver, targets[0].Semantic.PreferredMarkerKind);
		Assert.Equal(ResolvedActionKind.Talk, targets[0].Semantic.ActionKind);
		Assert.Equal("Talk to char:giver", targets[0].Explanation.PrimaryText);
		Assert.Equal(10f, targets[0].X);
		Assert.Equal(20f, targets[0].Y);
		Assert.Equal(30f, targets[0].Z);
	}

	[Fact]
	public void Resolve_QuestKey_WithItemGiverWithoutItem_UsesAcquisitionSourceSemantics()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:note")
			.AddCharacter("char:ghost")
			.AddSpawnPoint("spawn:ghost", scene: "Tutorial", x: 10f, y: 20f, z: 30f)
			.AddItemSource("item:note", "char:ghost", positionKeys: new[] { "spawn:ghost" })
			.AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "item:note" })
			.Build();
		var resolver = BuildResolver(guide);

		var targets = resolver.Resolve("quest:a", "Forest");

		var target = Assert.Single(targets);
		Assert.Equal("char:ghost", target.TargetNodeKey);
		Assert.Equal("spawn:ghost", target.SourceKey);
		Assert.Equal("Tutorial", target.Scene);
		Assert.Equal(QuestMarkerKind.Objective, target.Semantic.PreferredMarkerKind);
		Assert.Equal(ResolvedActionKind.Kill, target.Semantic.ActionKind);
		Assert.Equal("Kill char:ghost", target.Explanation.PrimaryText);
		Assert.Equal(10f, target.X);
		Assert.Equal(20f, target.Y);
		Assert.Equal(30f, target.Z);
	}

	[Fact]
	public void Resolve_CharacterKey_WithNoSpawns_ReturnsEmpty()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:manual", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.Build();
		var resolver = BuildResolver(guide);

		var targets = resolver.Resolve("char:manual", "Forest");

		Assert.Empty(targets);
	}

	[Fact]
	public void Resolve_QuestKey_ReusesCachedResultsWhenVersionUnchanged()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:fish")
			.AddWater("water:pond", scene: "Lake", x: 5f, y: 6f, z: 7f)
			.AddItemSource("item:fish", "water:pond", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) })
			.Build();
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var positionRegistry = CreatePositionRegistry(guide);
		var sourceResolver = new SourceResolver(
			guide, phases, unlocks, new StubLivePositionProvider(), positionRegistry);
		var resolver = new NavigationTargetResolver(
			guide,
			ResolutionTestFactory.BuildService(
				guide, frontier, sourceResolver,
				zoneRouter: null,
				positionRegistry: positionRegistry),
			null,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, null));

		var first = resolver.Resolve("quest:root", "Lake");
		var second = resolver.Resolve("quest:root", "Lake");

		Assert.Same(first, second);
	}

	[Fact]
	public void Resolve_QuestKey_RefreshesCachedResultsWhenEngineInvalidates()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:fish")
			.AddWater("water:pond", scene: "Lake", x: 5f, y: 6f, z: 7f)
			.AddItemSource(
				"item:fish", "water:pond",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.Water)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) })
			.Build();
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var positionRegistry = CreatePositionRegistry(guide);
		var sourceResolver = new SourceResolver(
			guide, phases, unlocks, new StubLivePositionProvider(), positionRegistry);
		var engine = new Engine<FactKey>();
		var resolver = new NavigationTargetResolver(
			guide,
			ResolutionTestFactory.BuildService(
				guide, frontier, sourceResolver,
				zoneRouter: null,
				engine: engine,
				positionRegistry: positionRegistry,
				questTracker: phases.State),
			null,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, null));

		var first = resolver.Resolve("quest:root", "Lake");

		// Mutate inventory so recompute yields a different result, then invalidate
		// the specific fact key. With backdating, a recompute that produces a
		// value-equal result is correctly memoised; the test verifies invalidation
		// is honoured when the value actually changes.
		phases.OnInventoryChanged(itemIndex: 0, newCount: 5);
		engine.InvalidateFacts(new[] { new FactKey(FactKind.InventoryItemCount, "item:fish") });

		var second = resolver.Resolve("quest:root", "Lake");

		Assert.NotSame(first, second);
	}

	[Fact]
	public void Resolve_QuestKey_RefreshesAfterFactInvalidation()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:giver", scene: "Forest", x: 10f, y: 20f, z: 30f)
			.AddCharacter("char:wolf", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItem("item:pelt")
			.AddItemSource("item:pelt", "char:wolf")
			.AddQuest(
				"quest:root",
				dbName: "ROOT",
				givers: new[] { "char:giver" },
				requiredItems: new[] { ("item:pelt", 1) }
			)
			.Build();
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			Array.Empty<string>(),
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var positionRegistry = CreatePositionRegistry(guide);
		var sourceResolver = new SourceResolver(
			guide, phases, unlocks, new StubLivePositionProvider(), positionRegistry);
		var engine = new Engine<FactKey>();
		var service = ResolutionTestFactory.BuildService(
			guide, frontier, sourceResolver,
			zoneRouter: null,
			engine: engine,
			positionRegistry: positionRegistry);
		var resolver = new NavigationTargetResolver(
			guide, service, null, positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, null));

		var initial = resolver.Resolve("quest:root", "Forest");
		var initialTarget = Assert.Single(initial);
		Assert.Equal("char:giver", initialTarget.TargetNodeKey);
		Assert.Equal(QuestMarkerKind.QuestGiver, initialTarget.Semantic.PreferredMarkerKind);

		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		engine.InvalidateFacts(new[]
		{
			new FactKey(FactKind.QuestActive, "ROOT"),
			new FactKey(FactKind.QuestCompleted, "ROOT"),
		});

		var refreshed = resolver.Resolve("quest:root", "Forest");
		var refreshedTarget = Assert.Single(refreshed);
		Assert.NotEqual(initialTarget.TargetNodeKey, refreshedTarget.TargetNodeKey);
		Assert.Equal("char:wolf", refreshedTarget.TargetNodeKey);
		Assert.Equal(QuestMarkerKind.Objective, refreshedTarget.Semantic.PreferredMarkerKind);
	}

	[Fact]
	public void Resolve_CharacterKey_WithSpawns_ReturnsTargetsAtSpawnPositions()
	{
		var guide = new CompiledGuideBuilder()
			.AddCharacter("char:npc", scene: "Forest", x: 0f, y: 0f, z: 0f)
			.AddSpawnPoint("spawn:npc:1", scene: "Forest", x: 10f, y: 20f, z: 30f)
			.AddSpawnPoint("spawn:npc:2", scene: "Desert", x: 40f, y: 50f, z: 60f)
			.AddEdge("char:npc", "spawn:npc:1", EdgeType.HasSpawn)
			.AddEdge("char:npc", "spawn:npc:2", EdgeType.HasSpawn)
			.Build();
		var resolver = BuildResolver(guide);

		var targets = resolver.Resolve("char:npc", "Forest");

		Assert.Equal(2, targets.Count);
		Assert.All(targets, t => Assert.Equal("char:npc", t.TargetNodeKey));
		Assert.All(targets, t => Assert.Equal(ResolvedActionKind.Talk, t.Semantic.ActionKind));
		Assert.All(
			targets,
			t => Assert.Equal(NavigationTargetKind.Character, t.Semantic.TargetKind)
		);
		Assert.All(targets, t => Assert.True(t.IsActionable));

		var sourceKeys = targets.Select(t => t.SourceKey).OrderBy(k => k).ToArray();
		Assert.Equal(new[] { "spawn:npc:1", "spawn:npc:2" }, sourceKeys);

		var spawn1 = targets.First(t => t.SourceKey == "spawn:npc:1");
		Assert.Equal(10f, spawn1.X);
		Assert.Equal(20f, spawn1.Y);
		Assert.Equal(30f, spawn1.Z);
		Assert.Equal("Forest", spawn1.Scene);

		var spawn2 = targets.First(t => t.SourceKey == "spawn:npc:2");
		Assert.Equal(40f, spawn2.X);
		Assert.Equal(50f, spawn2.Y);
		Assert.Equal(60f, spawn2.Z);
		Assert.Equal("Desert", spawn2.Scene);
	}

	[Fact]
	public void Resolve_ItemKey_WithSources_ReturnsTargetsAtSourcePositions()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:sword")
			.AddCharacter("char:goblin", scene: "Cave", x: 100f, y: 200f, z: 300f)
			.AddItemSource("item:sword", "char:goblin", edgeType: (byte)EdgeType.DropsItem)
			.Build();
		var resolver = BuildResolver(guide);

		var targets = resolver.Resolve("item:sword", "Cave");

		Assert.Single(targets);
		Assert.Equal("char:goblin", targets[0].TargetNodeKey);
		Assert.Equal(ResolvedActionKind.Collect, targets[0].Semantic.ActionKind);
		Assert.Equal(100f, targets[0].X);
		Assert.Equal(200f, targets[0].Y);
		Assert.Equal(300f, targets[0].Z);
	}

	[Fact]
	public void Resolve_ItemKey_WithMinedMiningSourcePosition_UsesMutableActionabilityTruth()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:coal")
			.AddMiningNode("mine:mined", scene: "Azure", x: 5f, y: 0f, z: 0f)
			.AddItemSource(
				"item:coal",
				"mine:mined",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.MiningNode)
			.Build();
		var resolver = BuildResolver(
			guide,
			positionRegistry: CreatePositionRegistry(
				guide,
				new Dictionary<string, bool> { ["mine:mined"] = false }));

		var targets = resolver.Resolve("item:coal", "Azure");

		var target = Assert.Single(targets);
		Assert.Equal("mine:mined", target.TargetNodeKey);
		Assert.Equal("mine:mined", target.SourceKey);
		Assert.Equal(ResolvedActionKind.Collect, target.Semantic.ActionKind);
		Assert.False(target.IsActionable);
	}

	[Fact]
	public void Resolve_ItemKey_WithNoSources_ReturnsEmpty()
	{
		var guide = new CompiledGuideBuilder().AddItem("item:none").Build();
		var resolver = BuildResolver(guide);

		Assert.Empty(resolver.Resolve("item:none", "Forest"));
	}

	[Fact]
	public void Resolve_MiningNodeKey_MinedNode_IsNonActionable()
	{
		var guide = new CompiledGuideBuilder()
			.AddMiningNode("mine:copper", scene: "Mountain", x: 10f, y: 20f, z: 30f)
			.Build();
		var resolver = BuildResolver(
			guide,
			positionRegistry: CreatePositionRegistry(
				guide,
				new Dictionary<string, bool> { ["mine:copper"] = false }));

		var targets = resolver.Resolve("mine:copper", "Mountain");

		var target = Assert.Single(targets);
		Assert.Equal("mine:copper", target.TargetNodeKey);
		Assert.Equal(10f, target.X);
		Assert.Equal(20f, target.Y);
		Assert.Equal(30f, target.Z);
		Assert.False(target.IsActionable);
	}

	[Fact]
	public void Resolve_QuestKey_WithAvailableAndMinedMiningSources_PrefersAvailableNode()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:coal")
			.AddMiningNode("mine:mined", scene: "Azure", x: 5f, y: 0f, z: 0f)
			.AddMiningNode("mine:available", scene: "Azure", x: 20f, y: 0f, z: 0f)
			.AddItemSource(
				"item:coal",
				"mine:mined",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.MiningNode)
			.AddItemSource(
				"item:coal",
				"mine:available",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.MiningNode)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:coal", 1) })
			.Build();
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var positionRegistry = CreatePositionRegistry(
			guide,
			new Dictionary<string, bool>
			{
				["mine:mined"] = false,
				["mine:available"] = true,
			});
		var sourceResolver = new SourceResolver(
			guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry
		);
		var resolver = new NavigationTargetResolver(
			guide,
			ResolutionTestFactory.BuildService(
				guide,
				frontier,
				sourceResolver,
				zoneRouter: null,
				positionRegistry: positionRegistry
			),
			null,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, null)
		);

		var targets = resolver.Resolve("quest:root", "Azure");

		Assert.Equal(2, targets.Count);
		Assert.Contains(
			targets,
			target => target.TargetNodeKey == "mine:mined" && !target.IsActionable
		);
		Assert.Contains(
			targets,
			target => target.TargetNodeKey == "mine:available" && target.IsActionable
		);

		var selected = NavigationTargetSelector.SelectBest(
            targets,
            0f,
            0f,
            0f,
            "Azure",
            SnapshotHarness.FromBuilder(new CompiledGuideBuilder()).Router);
		Assert.NotNull(selected);
		Assert.Equal("mine:available", selected!.Value.Target.TargetNodeKey);
	}

	[Fact]
	public void Resolve_WaterNode_ReturnsTargetAtNodePosition()
	{
		var guide = new CompiledGuideBuilder()
			.AddWater("water:pond", scene: "Lake", x: 5f, y: 6f, z: 7f)
			.Build();
		var resolver = BuildResolver(guide);

		var targets = resolver.Resolve("water:pond", "Lake");

		Assert.Single(targets);
		Assert.Equal("water:pond", targets[0].TargetNodeKey);
		Assert.Equal(ResolvedActionKind.Fish, targets[0].Semantic.ActionKind);
		Assert.Equal(5f, targets[0].X);
		Assert.Equal(6f, targets[0].Y);
		Assert.Equal(7f, targets[0].Z);
	}

	[Fact]
	public void Resolve_UnknownKey_ReturnsEmpty()
	{
		Assert.Empty(BuildResolver(new CompiledGuideBuilder().Build()).Resolve("missing", "Forest"));
	}

	[Fact]
	public void Resolve_QuestKey_UsesPrecomputedBlockingMapWhenProjectingNavigationTargets()
	{
		const string zoneA = "ZoneA";
		const string zoneB = "ZoneB";
		var guide = new CompiledGuideBuilder()
			.AddQuest("quest:root", dbName: "ROOT")
			.AddZone("zone:a", scene: zoneA)
			.AddZone("zone:b", scene: zoneB)
			.AddWater("water:pond", scene: zoneB, x: 5f, y: 6f, z: 7f)
			.Build();
		guide.TryGetNodeId("water:pond", out int waterNodeId);
		var semantic = new ResolvedActionSemantic(
			NavigationGoalKind.Generic,
			NavigationTargetKind.Object,
			ResolvedActionKind.Fish,
			goalNodeKey: null,
			goalQuantity: null,
			keywordText: null,
			payloadText: null,
			targetIdentityText: "Pond",
			contextText: null,
			rationaleText: null,
			zoneText: zoneB,
			availabilityText: null,
			preferredMarkerKind: QuestMarkerKind.Objective,
			markerPriority: 0);
		var projector = new QuestTargetProjector(guide, zoneRouter: null);

		var targets = projector.Project(
			new[]
			{
				new ResolvedTarget(
					targetNodeId: waterNodeId,
					positionNodeId: waterNodeId,
					role: ResolvedTargetRole.Objective,
					semantic: semantic,
					x: 5f,
					y: 6f,
					z: 7f,
					scene: zoneB,
					isLive: false,
					isActionable: true,
					questIndex: 0,
					requiredForQuestIndex: -1),
			},
			zoneA,
			new QuestTargetProjector.PrecomputedBlockingZoneMap(
				zoneA,
				new Dictionary<string, int>(StringComparer.Ordinal) { [zoneB.ToLowerInvariant()] = 42 }));

		Assert.True(Assert.Single(targets).IsBlockedPath);
	}

	[Fact]
	public void Resolve_QuestKey_IgnoresPrecomputedBlockingMapBoundToDifferentProjectedScene()
	{
		const string zoneA = "ZoneA";
		const string zoneB = "ZoneB";
		var guide = new CompiledGuideBuilder()
			.AddQuest("quest:root", dbName: "ROOT")
			.AddZone("zone:a", scene: zoneA)
			.AddZone("zone:b", scene: zoneB)
			.AddWater("water:pond", scene: zoneB, x: 5f, y: 6f, z: 7f)
			.Build();
		guide.TryGetNodeId("water:pond", out int waterNodeId);
		var semantic = new ResolvedActionSemantic(
			NavigationGoalKind.Generic,
			NavigationTargetKind.Object,
			ResolvedActionKind.Fish,
			goalNodeKey: null,
			goalQuantity: null,
			keywordText: null,
			payloadText: null,
			targetIdentityText: "Pond",
			contextText: null,
			rationaleText: null,
			zoneText: zoneB,
			availabilityText: null,
			preferredMarkerKind: QuestMarkerKind.Objective,
			markerPriority: 0);
		var projector = new QuestTargetProjector(guide, zoneRouter: null);

		var targets = projector.Project(
			new[]
			{
				new ResolvedTarget(
					targetNodeId: waterNodeId,
					positionNodeId: waterNodeId,
					role: ResolvedTargetRole.Objective,
					semantic: semantic,
					x: 5f,
					y: 6f,
					z: 7f,
					scene: zoneB,
					isLive: false,
					isActionable: true,
					questIndex: 0,
					requiredForQuestIndex: -1),
			},
			zoneA,
			new QuestTargetProjector.PrecomputedBlockingZoneMap(
				zoneB,
				new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase) { [zoneB] = 42 }));

		Assert.False(Assert.Single(targets).IsBlockedPath);
	}

	[Fact]
	public void Resolve_QuestKey_MarksZoneLockedSourceAsBlockedPath()
	{
		var builder = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "ZoneA")
			.AddZone("zone:b", scene: "ZoneB")
			.AddZoneLine(
				"zl:ab",
				scene: "ZoneA",
				destinationZoneKey: "zone:b",
				x: 10f,
				y: 0f,
				z: 5f
			)
			.AddQuest("quest:gate", dbName: "GATE")
			.AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
			.AddWater("water:pond", scene: "ZoneB", x: 5f, y: 6f, z: 7f)
			.AddItemSource(
				"item:fish",
				"water:pond",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.Water)
			.AddItem("item:fish")
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) });
		var harness = SnapshotHarness.FromSnapshot(
			builder.Build(),
			new StateSnapshot { CurrentZone = "ZoneA" }
		);
		var phases = new QuestPhaseTracker(harness.Guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(harness.Guide, phases);
		var unlocks = new UnlockPredicateEvaluator(harness.Guide, phases);
		var positionRegistry = CreatePositionRegistry(harness.Guide);
		var sourceResolver = new SourceResolver(
			harness.Guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry
		);
		var targetResolver = new NavigationTargetResolver(
			harness.Guide,
			ResolutionTestFactory.BuildService(
				harness.Guide,
				frontier,
				sourceResolver,
				zoneRouter: harness.Router,
				positionRegistry: positionRegistry
			),
			harness.Router,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(harness.Guide, harness.Router)
		);

		var targets = targetResolver.Resolve("quest:root", "ZoneA");

		Assert.True(Assert.Single(targets).IsBlockedPath);
	}

	[Fact]
	public void Resolve_DirectSourceNode_InLockedZone_MarksBlockedPath()
	{
		var builder = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "ZoneA")
			.AddZone("zone:b", scene: "ZoneB")
			.AddZoneLine(
				"zl:ab",
				scene: "ZoneA",
				destinationZoneKey: "zone:b",
				x: 10f,
				y: 0f,
				z: 5f
			)
			.AddQuest("quest:gate", dbName: "GATE")
			.AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
			.AddWater("water:pond", scene: "ZoneB", x: 5f, y: 6f, z: 7f);
		var harness = SnapshotHarness.FromSnapshot(
			builder.Build(),
			new StateSnapshot { CurrentZone = "ZoneA" }
		);
		var resolver = BuildResolver(harness.Guide, harness.Router);

		var targets = resolver.Resolve("water:pond", "ZoneA");

		Assert.True(Assert.Single(targets).IsBlockedPath);
	}

	[Fact]
	public void Resolve_QuestKey_WithLockedRoute_CutsOverToUnlockItemSource()
	{
		var builder = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "ZoneA")
			.AddZone("zone:b", scene: "ZoneB")
			.AddZoneLine(
				"zl:ab",
				scene: "ZoneA",
				destinationZoneKey: "zone:b",
				x: 10f,
				y: 0f,
				z: 5f
			)
			.AddItem("item:key")
			.AddCharacter("char:keykeeper", scene: "ZoneA", x: 2f, y: 3f, z: 4f)
			.AddItemSource(
				"item:key",
				"char:keykeeper",
				edgeType: (byte)EdgeType.GivesItem,
				sourceType: (byte)NodeType.Character
			)
			.AddEdge("item:key", "zl:ab", EdgeType.UnlocksZoneLine)
			.AddUnlockPredicate("zl:ab", "item:key", checkType: 1)
			.AddItem("item:fish")
			.AddWater("water:pond", scene: "ZoneB", x: 5f, y: 6f, z: 7f)
			.AddItemSource(
				"item:fish",
				"water:pond",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.Water
			)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) });
		var harness = SnapshotHarness.FromSnapshot(
			builder.Build(),
			new StateSnapshot { CurrentZone = "ZoneA", ActiveQuests = ["ROOT"] }
		);
		var phases = new QuestPhaseTracker(harness.Guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(harness.Guide, phases);
		var unlocks = new UnlockPredicateEvaluator(harness.Guide, phases);
		var positionRegistry = CreatePositionRegistry(harness.Guide);
		var sourceResolver = new SourceResolver(
			harness.Guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry,
			harness.Router
		);
		var resolver = new NavigationTargetResolver(
			harness.Guide,
			ResolutionTestFactory.BuildService(
				harness.Guide,
				frontier,
				sourceResolver,
				zoneRouter: harness.Router,
				positionRegistry: positionRegistry
			),
			harness.Router,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(harness.Guide, harness.Router)
		);

		var targets = resolver.Resolve("quest:root", "ZoneA");

		var target = Assert.Single(targets);
		Assert.Equal("char:keykeeper", target.TargetNodeKey);
		Assert.Equal("item:key", target.GoalNode.Node.Key);
		Assert.False(target.IsBlockedPath);
	}

	[Fact]
	public void Resolve_QuestKey_WithRepeatedLockedHopTargets_DedupesUnlockCutoverTargets()
	{
		var builder = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "ZoneA")
			.AddZone("zone:b", scene: "ZoneB")
			.AddZoneLine(
				"zl:ab",
				scene: "ZoneA",
				destinationZoneKey: "zone:b",
				x: 10f,
				y: 0f,
				z: 5f
			)
			.AddItem("item:key")
			.AddCharacter("char:keykeeper", scene: "ZoneA", x: 2f, y: 3f, z: 4f)
			.AddItemSource(
				"item:key",
				"char:keykeeper",
				edgeType: (byte)EdgeType.GivesItem,
				sourceType: (byte)NodeType.Character
			)
			.AddEdge("item:key", "zl:ab", EdgeType.UnlocksZoneLine)
			.AddUnlockPredicate("zl:ab", "item:key", checkType: 1)
			.AddItem("item:fish")
			.AddWater("water:pond:1", scene: "ZoneB", x: 5f, y: 6f, z: 7f)
			.AddWater("water:pond:2", scene: "ZoneB", x: 8f, y: 9f, z: 10f)
			.AddItemSource(
				"item:fish",
				"water:pond:1",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.Water
			)
			.AddItemSource(
				"item:fish",
				"water:pond:2",
				edgeType: (byte)EdgeType.YieldsItem,
				sourceType: (byte)NodeType.Water
			)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) });
		var harness = SnapshotHarness.FromSnapshot(
			builder.Build(),
			new StateSnapshot { CurrentZone = "ZoneA", ActiveQuests = ["ROOT"] }
		);

		var phases = new QuestPhaseTracker(harness.Guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(harness.Guide, phases);
		var unlocks = new UnlockPredicateEvaluator(harness.Guide, phases);
		var positionRegistry = CreatePositionRegistry(harness.Guide);
		var sourceResolver = new SourceResolver(
			harness.Guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry,
			harness.Router
		);
		var resolver = new NavigationTargetResolver(
			harness.Guide,
			ResolutionTestFactory.BuildService(
				harness.Guide,
				frontier,
				sourceResolver,
				zoneRouter: harness.Router,
				positionRegistry: positionRegistry
			),
			harness.Router,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(harness.Guide, harness.Router)
		);

		var targets = resolver.Resolve("quest:root", "ZoneA");

		var target = Assert.Single(targets);
		Assert.Equal("char:keykeeper", target.TargetNodeKey);
		Assert.Equal("item:key", target.GoalNode.Node.Key);
	}

	[Fact]
	public void Resolve_QuestKey_WithUnreadStepItem_UsesAcquisitionSourceSemantics()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:note")
			.AddCharacter("char:ghost", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:note", "char:ghost")
			.AddQuest("quest:a", dbName: "QUESTA")
			.AddStep("quest:a", StepLabels.Read, "item:note")
			.Build();
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var positionRegistry = CreatePositionRegistry(guide);
		var sourceResolver = new SourceResolver(
			guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry
		);
		var resolver = new NavigationTargetResolver(
			guide,
			ResolutionTestFactory.BuildService(
				guide,
				frontier,
				sourceResolver,
				zoneRouter: null,
				positionRegistry: positionRegistry
			),
			zoneRouter: null,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, null)
		);

		var targets = resolver.Resolve("quest:a", "Forest");

		var target = Assert.Single(targets);
		Assert.Equal("char:ghost", target.TargetNodeKey);
		Assert.Equal(ResolvedActionKind.Kill, target.Semantic.ActionKind);
		Assert.Equal("Kill char:ghost", target.Explanation.PrimaryText);
	}

	[Fact]
	public void Resolve_QuestKey_WithMixedDirectAndBlockedSources_PrefersDirectTargetAndProjectsAvailabilityPriority()
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
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var positionRegistry = CreatePositionRegistry(guide);
		var sourceResolver = new SourceResolver(
			guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry
		);
		var resolver = new NavigationTargetResolver(
			guide,
			ResolutionTestFactory.BuildService(
				guide,
				frontier,
				sourceResolver,
				zoneRouter: null,
				positionRegistry: positionRegistry
			),
			null,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, null)
		);

		var targets = resolver.Resolve("quest:root", "Forest");
		var availabilityPriority = typeof(ResolvedQuestTarget).GetProperty("AvailabilityPriority");

		Assert.Equal(2, targets.Count);
		Assert.Equal("char:plax", targets[0].TargetNodeKey);
		Assert.Null(targets[0].RequiredForQuestKey);
		Assert.Equal("char:elder", targets[1].TargetNodeKey);
		Assert.Equal("quest:key", targets[1].GoalNode.Node.Key);
		Assert.Equal("quest:key", targets[1].RequiredForQuestKey);
		Assert.NotNull(availabilityPriority);
		Assert.Equal("Immediate", availabilityPriority!.GetValue(targets[0])?.ToString());
		Assert.Equal("PrerequisiteFallback", availabilityPriority.GetValue(targets[1])?.ToString());
	}

	[Fact]
	public void Resolve_QuestKey_WithLockedRouteToQuestUnlock_CutsOverToUnlockQuestFrontier()
	{
		const string zoneA = "Stowaway";
		const string zoneB = "StowawayPortal";
		var builder = new CompiledGuideBuilder()
			.AddZone("zone:stowaway", scene: zoneA)
			.AddZone("zone:stowawayportal", scene: zoneB)
			.AddZoneLine(
				"zl:portal",
				scene: zoneA,
				destinationZoneKey: "zone:stowawayportal",
				x: 425.15f,
				y: 71.73f,
				z: 532.23f
			)
			.AddItem("item:eldrich")
			.AddCharacter("char:keeper", scene: zoneB, x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:eldrich", "char:keeper", edgeType: (byte)EdgeType.DropsItem)
			.AddCharacter("char:lucian", scene: zoneA, x: 10f, y: 11f, z: 12f)
			.AddQuest("quest:ritual", dbName: "RITUAL", givers: new[] { "char:lucian" })
			.AddEdge("quest:ritual", "zl:portal", EdgeType.UnlocksZoneLine)
			.AddUnlockPredicate("zl:portal", "quest:ritual")
			.AddQuest("quest:eldrich", dbName: "ELDRICH", requiredItems: new[] { ("item:eldrich", 1) });
		var harness = SnapshotHarness.FromSnapshot(
			builder.Build(),
			new StateSnapshot { CurrentZone = zoneA, ActiveQuests = ["ELDRICH"] }
		);
		var phases = new QuestPhaseTracker(harness.Guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ELDRICH" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(harness.Guide, phases);
		var unlocks = new UnlockPredicateEvaluator(harness.Guide, phases);
		var positionRegistry = CreatePositionRegistry(harness.Guide);
		var sourceResolver = new SourceResolver(
			harness.Guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry,
			harness.Router
		);
		var resolver = new NavigationTargetResolver(
			harness.Guide,
			ResolutionTestFactory.BuildService(
				harness.Guide,
				frontier,
				sourceResolver,
				zoneRouter: harness.Router,
				positionRegistry: positionRegistry
			),
			harness.Router,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(harness.Guide, harness.Router)
		);

		var targets = resolver.Resolve("quest:eldrich", zoneA);
		var target = Assert.Single(targets);

		Assert.Equal("char:lucian", target.TargetNodeKey);
		Assert.Equal(zoneA, target.Scene);
		Assert.Equal("quest:ritual", target.GoalNode.Node.Key);
		Assert.Equal("quest:ritual", target.RequiredForQuestKey);
		Assert.False(target.IsBlockedPath);
	}

	[Fact]
	public void Resolve_QuestKey_CollapsesCrossZoneTargetsToOnePerSceneAndBlockedState()
	{
		const string zoneA = "ZoneA";
		const string zoneB = "ZoneB";
		const string zoneC = "ZoneC";
		var builder = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: zoneA)
			.AddZone("zone:b", scene: zoneB)
			.AddZone("zone:c", scene: zoneC)
			.AddZoneLine("zl:ab", scene: zoneA, destinationZoneKey: "zone:b", x: 10f, y: 0f, z: 0f)
			.AddZoneLine("zl:ac", scene: zoneA, destinationZoneKey: "zone:c", x: 20f, y: 0f, z: 0f)
			.AddItem("item:fish")
			.AddWater("water:a", scene: zoneA, x: 1f, y: 0f, z: 0f)
			.AddWater("water:b:1", scene: zoneB, x: 2f, y: 0f, z: 0f)
			.AddWater("water:b:2", scene: zoneB, x: 3f, y: 0f, z: 0f)
			.AddWater("water:b:3", scene: zoneB, x: 4f, y: 0f, z: 0f)
			.AddWater("water:c:1", scene: zoneC, x: 5f, y: 0f, z: 0f)
			.AddWater("water:c:2", scene: zoneC, x: 6f, y: 0f, z: 0f)
			.AddItemSource("item:fish", "water:a", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
			.AddItemSource("item:fish", "water:b:1", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
			.AddItemSource("item:fish", "water:b:2", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
			.AddItemSource("item:fish", "water:b:3", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
			.AddItemSource("item:fish", "water:c:1", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
			.AddItemSource("item:fish", "water:c:2", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
			.AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) });
		var harness = SnapshotHarness.FromSnapshot(
			builder.Build(),
			new StateSnapshot { CurrentZone = zoneA, ActiveQuests = ["ROOT"] }
		);
		var phases = new QuestPhaseTracker(harness.Guide);
		phases.Initialize(
			Array.Empty<string>(),
			new[] { "ROOT" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(harness.Guide, phases);
		var unlocks = new UnlockPredicateEvaluator(harness.Guide, phases);
		var positionRegistry = CreatePositionRegistry(harness.Guide);
		var sourceResolver = new SourceResolver(
			harness.Guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry
		);
		var resolver = new NavigationTargetResolver(
			harness.Guide,
			ResolutionTestFactory.BuildService(
				harness.Guide,
				frontier,
				sourceResolver,
				zoneRouter: harness.Router,
				positionRegistry: positionRegistry
			),
			harness.Router,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(harness.Guide, harness.Router)
		);

		var targets = resolver.Resolve("quest:root", zoneA);

		Assert.Equal(3, targets.Count);
		Assert.Contains(targets, target => target.TargetNodeKey == "water:a");
		Assert.Single(targets, target => string.Equals(target.Scene, zoneB, StringComparison.OrdinalIgnoreCase));
		Assert.Single(targets, target => string.Equals(target.Scene, zoneC, StringComparison.OrdinalIgnoreCase));
	}

	private static NavigationTargetResolver BuildResolver(
		CompiledGuideModel guide,
		ZoneRouter? router = null,
		PositionResolverRegistry? positionRegistry = null
	)
	{
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(
			Array.Empty<string>(),
			Array.Empty<string>(),
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		positionRegistry ??= CreatePositionRegistry(guide);
		var sourceResolver = new SourceResolver(
			guide,
			phases,
			unlocks,
			new StubLivePositionProvider(),
			positionRegistry,
			router
		);
		return new NavigationTargetResolver(
			guide,
			ResolutionTestFactory.BuildService(
				guide,
				frontier,
				sourceResolver,
				zoneRouter: router,
				positionRegistry: positionRegistry
			),
			router,
			positionRegistry,
			ResolutionTestFactory.BuildProjector(guide, router)
		);
	}

	private static PositionResolverRegistry CreatePositionRegistry(
		CompiledGuideModel guide,
		IReadOnlyDictionary<string, bool>? actionabilityByKey = null
	)
	{
		return TestPositionResolvers.Create(guide, actionabilityByKey);
	}
}
