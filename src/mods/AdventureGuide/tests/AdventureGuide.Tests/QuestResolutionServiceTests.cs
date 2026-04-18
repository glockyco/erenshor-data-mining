using System.Reflection;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests;

public sealed class QuestResolutionServiceTests
{
    [Fact]
    public void QuestResolutionService_ExposesBatchResolveAndFactInvalidationApis()
    {
        var serviceType = typeof(NavigationTargetResolver).Assembly.GetType(
            "AdventureGuide.Resolution.QuestResolutionService"
        );

        Assert.NotNull(serviceType);
        Assert.NotNull(
            serviceType!.GetMethod(
                "ResolveBatch",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                null,
                new[]
                {
                    typeof(IEnumerable<string>),
                    typeof(string),
                    typeof(IResolutionTracer),
                },
                null
            )
        );
        Assert.NotNull(
            serviceType.GetMethod(
                "InvalidateFacts",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic
            )
        );
    }

    [Fact]
    public void QuestResolutionRecord_ExposesSharedSurfaceInputs()
    {
        var recordType = typeof(NavigationTargetResolver).Assembly.GetType(
            "AdventureGuide.Resolution.QuestResolutionRecord"
        );

        Assert.NotNull(recordType);
        Assert.NotNull(recordType!.GetProperty("QuestKey"));
        Assert.NotNull(recordType.GetProperty("Frontier"));
        Assert.NotNull(recordType.GetProperty("CompiledTargets"));
    }

    [Fact]
    public void SurfaceConsumers_DoNotExposeSourceResolverConstructionShortcuts()
    {
        Assert.DoesNotContain(
            typeof(NavigationTargetResolver).GetConstructors(
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic
            ),
            ctor => HasParameter(ctor, typeof(SourceResolver)) || HasParameter(ctor, typeof(EffectiveFrontier))
        );
        Assert.DoesNotContain(
            typeof(TrackerSummaryResolver).GetConstructors(
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic
            ),
            ctor => HasParameter(ctor, typeof(SourceResolver)) || HasParameter(ctor, typeof(EffectiveFrontier))
        );
        Assert.DoesNotContain(
            typeof(MarkerQuestTargetResolver).GetConstructors(
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic
            ),
            ctor => HasParameter(ctor, typeof(SourceResolver)) || HasParameter(ctor, typeof(EffectiveFrontier))
        );
    }

    private static bool HasParameter(ConstructorInfo ctor, Type parameterType)
    {
        foreach (var parameter in ctor.GetParameters())
        {
            if (parameter.ParameterType == parameterType)
                return true;
        }

        return false;
    }

    [Fact]
    public void QuestResolutionService_ExposesSharedSessionResolveOverload()
    {
        var serviceType = typeof(NavigationTargetResolver).Assembly.GetType(
            "AdventureGuide.Resolution.QuestResolutionService"
        );

        Assert.NotNull(serviceType);
        Assert.NotNull(
            serviceType!.GetMethod(
                "ResolveQuest",
                System.Reflection.BindingFlags.Instance
                    | System.Reflection.BindingFlags.Public
                    | System.Reflection.BindingFlags.NonPublic,
                null,
                new[]
                {
                    typeof(string),
                    typeof(string),
                    typeof(SourceResolver.ResolutionSession),
                    typeof(IResolutionTracer),
                },
                null
            )
        );
    }

    [Fact]
    public void ResolveQuest_TraversesFrontierOncePerQuest()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
            .AddItem("item:root")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:root", 1) })
            .AddItemSource(
                "item:root",
                "char:leaf",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .Build();
        var phases = new QuestPhaseTracker(guide);
        phases.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
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
        var service = new QuestResolutionService(guide, frontier, sourceResolver, null);
        var tracer = new CountingTracer();

        var record = service.ResolveQuest("quest:root", "Town", tracer);

        Assert.Single(record.Frontier);
        Assert.Equal(1, tracer.FrontierEntryCount);
    }

    [Fact]
    public async Task ResolveBatch_WithSharedRewardSubtrees_CompletesWithinBudget()
    {
        const int depth = 20;
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
        var service = new QuestResolutionService(guide, frontier, sourceResolver, null);

        var resolveTask = System.Threading.Tasks.Task.Run(
            () => service.ResolveBatch(new[] { "quest:root:a", "quest:root:b" }, "Town")
        );
        // This is a regression guard against combinatorial blow-ups, not a
        // microbenchmark. Keep the budget loose enough to stay stable across
        // developer machines.
        var completed = await System.Threading.Tasks.Task.WhenAny(
            resolveTask,
            System.Threading.Tasks.Task.Delay(System.TimeSpan.FromMilliseconds(3000))
        );


        Assert.Same(resolveTask, completed);
        Assert.Equal(2, (await resolveTask).Count);
    }

    private sealed class CountingTracer : IResolutionTracer
    {
        public int FrontierEntryCount { get; private set; }

        public void OnQuestPhase(int questIndex, string? dbName, string phase) { }

        public void OnFrontierEntry(
            int questIndex,
            string? questDbName,
            string phase,
            int requiredForQuestIndex
        )
        {
            FrontierEntryCount++;
        }

        public void OnTargetMaterialized(
            int targetNodeId,
            int positionNodeId,
            string role,
            string? scene,
            bool isActionable
        ) { }

        public void OnHostileDropFilter(int itemIndex, int totalSources, int suppressedCount) { }

        public void OnUnlockEvaluation(int targetNodeId, bool isUnlocked) { }

        public void OnResolveBegin(string nodeKey) { }

        public void OnResolveEnd(int targetCount) { }
    }
}
