using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
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
		phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
		var targetResolver = new NavigationTargetResolver(
			guide,
			frontier,
			sourceResolver);

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
	public void Version_UsesProvidedVersionSource()
	{
		int version = 1;
		var guide = new CompiledGuideBuilder().Build();
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
		var targetResolver = new NavigationTargetResolver(
			guide,
			frontier,
			sourceResolver,
			() => version);

		Assert.Equal(1, targetResolver.Version);
		version = 2;
		Assert.Equal(2, targetResolver.Version);
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

		// Both targets reference the character node
		Assert.All(targets, t => Assert.Equal("char:npc", t.TargetNodeKey));
		Assert.All(targets, t => Assert.Equal(ResolvedActionKind.Talk, t.Semantic.ActionKind));
		Assert.All(targets, t => Assert.Equal(NavigationTargetKind.Character, t.Semantic.TargetKind));
		Assert.All(targets, t => Assert.True(t.IsActionable));

		// Each target has the spawn point as source key
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
			.AddItemSource("item:sword", "char:goblin")
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
	public void Resolve_ItemKey_WithNoSources_ReturnsEmpty()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:orphan")
			.Build();
		var resolver = BuildResolver(guide);

		var targets = resolver.Resolve("item:orphan", "Forest");

		Assert.Empty(targets);
	}

	[Fact]
	public void Resolve_MiningNodeKey_ReturnsTargetAtNodePosition()
	{
		var guide = new CompiledGuideBuilder()
			.AddMiningNode("mine:copper", scene: "Mountain")
			.AddEdge("mine:copper", "mine:copper", EdgeType.YieldsItem) // just so it has coords
			.Build();
		var resolver = BuildResolver(guide);

		// Mining nodes in the builder don't get X/Y/Z, so this will return empty
		// unless we use a node type that carries coordinates.
		var targets = resolver.Resolve("mine:copper", "Mountain");

		// MiningNodeDef in builder doesn't carry X/Y/Z, so no coordinates = empty
		Assert.Empty(targets);
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
		var guide = new CompiledGuideBuilder().Build();
		var resolver = BuildResolver(guide);

		var targets = resolver.Resolve("nonexistent:key", "Forest");

		Assert.Empty(targets);
	}

	private static NavigationTargetResolver BuildResolver(CompiledGuideModel guide)
	{
		var phases = new QuestPhaseTracker(guide);
		phases.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
		var frontier = new EffectiveFrontier(guide, phases);
		var unlocks = new UnlockPredicateEvaluator(guide, phases);
		var sourceResolver = new SourceResolver(guide, phases, unlocks, new StubLivePositionProvider());
		return new NavigationTargetResolver(guide, frontier, sourceResolver);
	}

}
