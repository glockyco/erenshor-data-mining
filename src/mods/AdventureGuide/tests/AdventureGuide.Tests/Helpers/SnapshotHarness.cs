using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.State;
using AdventureGuide.State.Resolvers;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Wires an <see cref="EntityGraph"/> + <see cref="StateSnapshot"/> (or empty state)
/// into the canonical plan / resolution / unlock pipeline for testing without
/// reading live <c>GameData</c>.
/// </summary>
public sealed class SnapshotHarness
{
    public EntityGraph Graph { get; }
    public GameState GameState { get; }
    public QuestStateTracker Tracker { get; }
    public UnlockEvaluator Unlocks { get; }
    public ZoneRouter Router { get; }
    public QuestPlanBuilder PlanBuilder { get; }
    private SnapshotHarness(EntityGraph graph, GameState gameState,
        QuestStateTracker tracker, UnlockEvaluator unlocks,
        ZoneRouter router, QuestPlanBuilder planBuilder)
    {
        Graph = graph;
        GameState = gameState;
        Tracker = tracker;
        Unlocks = unlocks;
        Router = router;
        PlanBuilder = planBuilder;
    }

    /// <summary>Builds a canonical quest plan for a quest.</summary>
    public QuestPlan BuildPlan(string questKey) => PlanBuilder.Build(questKey);

    /// <summary>Builds a canonical plan rooted at any graph node.</summary>
    public QuestPlan BuildNodePlan(string nodeKey) => PlanBuilder.BuildNode(nodeKey);

    /// <summary>Computes the actionable frontier from a canonical quest plan.</summary>
    public IReadOnlyList<FrontierRef> ComputePlanFrontier(QuestPlan plan)
        => FrontierResolver.ComputeFrontier(plan, GameState);

    /// <summary>
    /// Creates a fully wired harness from a graph and a state snapshot.
    /// No live game data is accessed.
    /// </summary>
    public static SnapshotHarness FromSnapshot(EntityGraph graph, StateSnapshot snapshot)
    {
        var depEngine = new GuideDependencyEngine();
        var indexes = new GraphIndexes(graph);
        var tracker = new QuestStateTracker(graph, indexes, depEngine);

        tracker.LoadState(
            snapshot.CurrentZone,
            snapshot.ActiveQuests,
            snapshot.CompletedQuests,
            snapshot.Inventory,
            snapshot.Keyring);

        var gameState = new GameState(graph);
        gameState.Register(NodeType.Quest, new QuestStateResolver(tracker));
        gameState.Register(NodeType.Item, new ItemStateResolver(tracker));

        // For live-world node types, register a resolver that returns
        // NodeState from the snapshot's liveNodeStates map.
        var liveResolver = new SnapshotLiveResolver(snapshot.LiveNodeStates);
        gameState.Register(NodeType.Character, liveResolver);
        gameState.Register(NodeType.SpawnPoint, liveResolver);
        gameState.Register(NodeType.MiningNode, liveResolver);
        gameState.Register(NodeType.ItemBag, liveResolver);
        gameState.Register(NodeType.Door, liveResolver);

        // ZoneLine uses UnlockEvaluator, which we wire below.
        var unlocks = new UnlockEvaluator(graph, gameState, tracker);
        gameState.Register(NodeType.ZoneLine, new ZoneLineStateResolver(unlocks));

        var router = new ZoneRouter(graph, unlocks);
        router.Rebuild();

        var planBuilder = new QuestPlanBuilder(graph, gameState, router, tracker, unlocks);

        return new SnapshotHarness(graph, gameState, tracker, unlocks, router, planBuilder);
    }

    /// <summary>Creates a harness from a builder with empty (all-default) state.</summary>
    public static SnapshotHarness FromGraph(TestGraphBuilder builder)
        => FromSnapshot(builder.Build(), new StateSnapshot());
}

/// <summary>
/// <see cref="INodeStateResolver"/> that returns <see cref="NodeState"/> from a
/// snapshot's <see cref="LiveNodeState"/> map. Nodes not in the map get
/// <see cref="NodeState.Unknown"/>.
/// </summary>
internal sealed class SnapshotLiveResolver : INodeStateResolver
{
    private readonly Dictionary<string, LiveNodeState> _states;

    public SnapshotLiveResolver(Dictionary<string, LiveNodeState> states)
    {
        _states = states ?? new();
    }

    public NodeState Resolve(Node node)
    {
        if (!_states.TryGetValue(node.Key, out var live))
            return NodeState.Unknown;

        return live.State switch
        {
            "alive" => NodeState.Alive,
            "dead" => new SpawnDead(0f),
            "disabled" => NodeState.Disabled,
            "night_locked" => NodeState.NightLocked,
            "mine_available" => NodeState.MineAvailable,
            "bag_available" => NodeState.BagAvailable,
            "bag_gone" => NodeState.BagGone,
            "door_unlocked" => NodeState.Unlocked,
            "door_locked" => new DoorLocked("key"),
            "door_closed" => new DoorClosed(),
            _ => NodeState.Unknown,
        };
    }
}
