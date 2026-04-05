using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.State.Resolvers;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestResolutionServicePositionInvalidationTests
{
    [Fact]
    public void ApplyChangeSet_InvalidatesCachedSourcePositions()
    {
        var graph = new TestGraphBuilder()
            .AddMiningNode("mining:test", "Mineral Deposit", scene: "ZoneA")
            .Build();
        var miningNode = graph.GetNode("mining:test")!;
        miningNode.X = 10f;
        miningNode.Y = 20f;
        miningNode.Z = 30f;

        var dependencies = new GuideDependencyEngine();
        var indexes = new GraphIndexes(graph);
        var tracker = new QuestStateTracker(graph, indexes, dependencies);
        tracker.LoadState(
            currentZone: "ZoneA",
            activeQuests: Array.Empty<string>(),
            completedQuests: Array.Empty<string>(),
            inventoryCounts: new Dictionary<string, int>(),
            keyringItemKeys: Array.Empty<string>());

        var gameState = new GameState(graph);
        gameState.Register(NodeType.Quest, new QuestStateResolver(tracker));
        gameState.Register(NodeType.Item, new ItemStateResolver(tracker));
        gameState.Register(
            NodeType.MiningNode,
            new SnapshotLiveResolver(new Dictionary<string, LiveNodeState>
            {
                ["mining:test"] = new() { State = "mine_available" },
            }));

        var unlocks = new UnlockEvaluator(graph, gameState, tracker);
        gameState.Register(NodeType.ZoneLine, new ZoneLineStateResolver(unlocks));
        var router = new ZoneRouter(graph, unlocks);
        router.Rebuild();

        var registry = new PositionResolverRegistry(graph);
        var miningResolver = new ToggleMiningResolver(isActionable: true);
        registry.Register(NodeType.MiningNode, miningResolver);
        var positionCache = new SourcePositionCache(registry, graph);
        var planBuilder = new QuestPlanBuilder(graph, gameState, router, tracker, unlocks);
        var sourceIndex = new CompiledSourceIndex(graph);
        var resolution = new QuestResolutionService(
            graph,
            tracker,
            gameState,
            planBuilder,
            dependencies,
            sourceIndex,
            positionCache,
            unlocks,
            router,

            new TestResolutionLiveState());
        var first = Assert.Single(resolution.ResolveTargetsForNavigation("mining:test"));
        Assert.True(first.IsActionable);
        Assert.Equal(1, miningResolver.CallCount);

        miningResolver.IsActionable = false;
        resolution.ApplyChangeSet(new GuideChangeSet(
            inventoryChanged: false,
            questLogChanged: false,
            sceneChanged: false,
            liveWorldChanged: true,
            changedItemKeys: Array.Empty<string>(),
            changedQuestDbNames: Array.Empty<string>(),
            affectedQuestKeys: Array.Empty<string>(),
            changedFacts: new[]
            {
                new GuideFactKey(GuideFactKind.SourceState, "mining:test"),
            }));

        var second = Assert.Single(resolution.ResolveTargetsForNavigation("mining:test"));
        Assert.False(second.IsActionable);
        Assert.Equal(2, miningResolver.CallCount);
    }

    private sealed class ToggleMiningResolver : IPositionResolver
    {
        public bool IsActionable { get; set; }
        public int CallCount { get; private set; }

        public ToggleMiningResolver(bool isActionable)
        {
            IsActionable = isActionable;
        }

        public void Resolve(Node node, List<ResolvedPosition> results)
        {
            CallCount++;
            results.Add(new ResolvedPosition(
                node.X ?? 0f,
                node.Y ?? 0f,
                node.Z ?? 0f,
                node.Scene,
                node.Key,
                isActionable: IsActionable));
        }
    }

}
