using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Frontier;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TrackerDiagnosticsTests
{
    [Fact]
    public void Resolve_RecordsPreferredTargetUsageInSnapshot()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ore")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:ore", 1) })
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
        var resolver = new TrackerSummaryResolver(
    guide,
    phases,
    ResolutionTestFactory.BuildService(guide, frontier, sourceResolver, phases, zoneRouter: null),
    new DiagnosticsCore(64, 64, 8, IncidentThresholds.Disabled)
);
        var dependencyEngine = new GuideDependencyEngine();
        var tracker = new QuestStateTracker(guide);
        tracker.LoadState(
            "Forest",
            new[] { "ROOT" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var goalNode = new ResolvedNodeContext(
            "item:ore",
            new Node
            {
                Key = "item:ore",
                Type = NodeType.Item,
                DisplayName = "Iron Ore",
            }
        );
        var targetNode = new ResolvedNodeContext(
            "mine:ore",
            new Node
            {
                Key = "mine:ore",
                Type = NodeType.MiningNode,
                DisplayName = "Mineral Deposit",
            }
        );
        var semantic = new ResolvedActionSemantic(
            NavigationGoalKind.CollectItem,
            NavigationTargetKind.Object,
            ResolvedActionKind.Mine,
            goalNodeKey: "item:ore",
            goalQuantity: 1,
            keywordText: null,
            payloadText: "Iron Ore",
            targetIdentityText: "Mineral Deposit",
            contextText: null,
            rationaleText: null,
            zoneText: null,
            availabilityText: null,
            preferredMarkerKind: QuestMarkerKind.Objective,
            markerPriority: 10
        );
        var preferredTarget = new ResolvedQuestTarget(
            "mine:ore",
            "Forest",
            "mine:ore",
            goalNode,
            targetNode,
            semantic,
            NavigationExplanationBuilder.Build(semantic, goalNode, targetNode),
            x: 1f,
            y: 2f,
            z: 3f,
            isActionable: true
        );

        var summary = resolver.Resolve("quest:root", "ROOT", "Forest", preferredTarget, tracker);

        var snapshot = resolver.ExportDiagnosticsSnapshot();
        Assert.NotNull(summary);
        Assert.True(snapshot.LastResolveUsedPreferredTarget);
    }

    [Fact]
    public void ProjectRoot_RecordsPruneAndCycleCounts()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:lucian")
            .AddUnlockPredicate("char:lucian", "quest:root")
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:lucian" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory.BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty, diagnostics: new DiagnosticsCore(64, 64, 8, IncidentThresholds.Disabled)).Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);

        var snapshot = projector.ExportDiagnosticsSnapshot();
        Assert.True(snapshot.LastProjectedNodeCount >= roots.Count);
        Assert.True(snapshot.LastCyclePruneCount >= 1);
    }

    private static int FindQuestIndex(AdventureGuide.CompiledGuide.CompiledGuide guide, string key)
    {
        Assert.True(guide.TryGetNodeId(key, out int nodeId));
        for (int questIndex = 0; questIndex < guide.QuestCount; questIndex++)
        {
            if (guide.QuestNodeId(questIndex) == nodeId)
                return questIndex;
        }

        throw new InvalidOperationException($"Quest '{key}' not found in compiled guide.");
    }
}
