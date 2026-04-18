using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class MarkerQuestTargetResolverTests
{
    [Fact]
    public void Resolve_ReturnsCompiledTargetsForQuestDbName()
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
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            unlocks,
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new MarkerQuestTargetResolver(
    guide,
    ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null)
);

        var targets = resolver.Resolve("QUESTA", "Forest");

        Assert.Single(targets);
        Assert.Equal(QuestMarkerKind.QuestGiver, targets[0].Semantic.PreferredMarkerKind);
        Assert.Equal(10f, targets[0].X);
        Assert.Equal(20f, targets[0].Y);
        Assert.Equal(30f, targets[0].Z);
    }

    [Fact]
    public void Resolve_MixedDirectAndBlockedSources_KeepsDirectTargetsAheadOfFallbacks()
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
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            unlocks,
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new MarkerQuestTargetResolver(
    guide,
    ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null)
);

        var targets = resolver.Resolve("ROOT", "Forest");

        Assert.Equal(2, targets.Count);
        Assert.Equal("char:plax", guide.GetNodeKey(targets[0].TargetNodeId));
        Assert.Equal(ResolvedTargetRole.Objective, targets[0].Role);
        Assert.Equal("char:elder", guide.GetNodeKey(targets[1].TargetNodeId));
        Assert.Equal(ResolvedTargetRole.Giver, targets[1].Role);
    }

    [Fact]
    public void Resolve_ThrowsWhenQuestDbNameMissingFromCompiledGuide()
    {
        var guide = new CompiledGuideBuilder().Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var unlocks = new UnlockPredicateEvaluator(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            unlocks,
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new MarkerQuestTargetResolver(
    guide,
    ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null)
);

        var ex = Assert.Throws<InvalidOperationException>(
            () => resolver.Resolve("MISSING", "Forest")
        );

        Assert.Contains("MISSING", ex.Message, System.StringComparison.Ordinal);
    }

    [Fact]
    public async Task Resolve_WithSharedResolutionSession_ReusesSharedSubgraphsAcrossQuests()
    {
        const int depth = 18;
        var builder = new CompiledGuideBuilder()
            .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
            .AddQuest("quest:root:a", dbName: "ROOTA", requiredItems: new[] { ("item:0", 1) })
            .AddQuest("quest:root:b", dbName: "ROOTB", requiredItems: new[] { ("item:0", 1) });

        for (int i = 0; i <= depth; i++)
            builder.AddItem($"item:{i}");

        var activeQuests = new List<string> { "ROOTA", "ROOTB" };
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
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            activeQuests,
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var frontier = new EffectiveFrontier(guide, phases);
        var sourceResolver = new SourceResolver(
            guide,
            phases,
            new UnlockPredicateEvaluator(guide, phases),
            new StubLivePositionProvider(),
            TestPositionResolvers.Create(guide)
        );
        var resolver = new MarkerQuestTargetResolver(
    guide,
    ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, zoneRouter: null)
);
        var session = new SourceResolver.ResolutionSession();

        var resolveTask = System.Threading.Tasks.Task.Run(() =>
        {
            resolver.Resolve("ROOTA", "Town", session);
            return resolver.Resolve("ROOTB", "Town", session);
        });
        var completed = await System.Threading.Tasks.Task.WhenAny(
            resolveTask,
            System.Threading.Tasks.Task.Delay(System.TimeSpan.FromMilliseconds(3000))
        );

        Assert.Same(resolveTask, completed);
        Assert.NotEmpty(await resolveTask);
    }
}
