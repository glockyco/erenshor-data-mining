using System.Reflection;
using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.State;
using AdventureGuide.State.Resolvers;
using AdventureGuide.Views;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Wires an <see cref="EntityGraph"/> + <see cref="StateSnapshot"/> (or empty state)
/// into the full view-build / frontier / unlock pipeline for testing.
///
/// Uses reflection to populate <see cref="QuestStateTracker"/> internals directly,
/// bypassing <see cref="QuestStateTracker.SyncFromGameData"/> which reads live
/// <c>GameData.*</c> statics.
/// </summary>
public sealed class SnapshotHarness
{
    public EntityGraph Graph { get; }
    public GameState GameState { get; }
    public QuestStateTracker Tracker { get; }
    public UnlockEvaluator Unlocks { get; }
    public ZoneRouter Router { get; }
    public QuestViewBuilder ViewBuilder { get; }
    public QuestPlanBuilder PlanBuilder { get; }

    private SnapshotHarness(EntityGraph graph, GameState gameState,
        QuestStateTracker tracker, UnlockEvaluator unlocks,
        ZoneRouter router, QuestViewBuilder viewBuilder, QuestPlanBuilder planBuilder)
    {
        Graph = graph;
        GameState = gameState;
        Tracker = tracker;
        Unlocks = unlocks;
        Router = router;
        ViewBuilder = viewBuilder;
        PlanBuilder = planBuilder;
    }

    /// <summary>Builds a full dependency view tree for a quest.</summary>
    public ViewNode? BuildViewTree(string questKey) => ViewBuilder.Build(questKey);

    /// <summary>Computes the actionable frontier from a pre-built view tree.</summary>
    public List<EntityViewNode> ComputeFrontier(ViewNode? tree)
        => tree != null ? FrontierComputer.ComputeFrontier(tree, GameState) : new();

    /// <summary>Builds a canonical quest plan for a quest.</summary>
    public QuestPlan BuildPlan(string questKey) => PlanBuilder.Build(questKey);

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

        // Populate tracker from snapshot without calling SyncFromGameData.
        PopulateTracker(tracker, snapshot);

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

        var viewBuilder = new QuestViewBuilder(graph, gameState, router, tracker, unlocks);
        var planBuilder = new QuestPlanBuilder(graph);

        return new SnapshotHarness(graph, gameState, tracker, unlocks, router, viewBuilder, planBuilder);
    }

    /// <summary>Creates a harness from a builder with empty (all-default) state.</summary>
    public static SnapshotHarness FromGraph(TestGraphBuilder builder)
        => FromSnapshot(builder.Build(), new StateSnapshot());

    private static void PopulateTracker(QuestStateTracker tracker, StateSnapshot snapshot)
    {
        const BindingFlags NonPublicInstance = BindingFlags.NonPublic | BindingFlags.Instance;

        // Current zone
        SetField(tracker, "_currentZone", snapshot.CurrentZone ?? "", NonPublicInstance);

        // Active quests
        if (GetField<HashSet<string>>(tracker, "_activeQuests", NonPublicInstance) is { } activeSet)
        {
            activeSet.Clear();
            foreach (var q in snapshot.ActiveQuests)
                activeSet.Add(q);
        }

        // Completed quests
        if (GetField<HashSet<string>>(tracker, "_completedQuests", NonPublicInstance) is { } completedSet)
        {
            completedSet.Clear();
            foreach (var q in snapshot.CompletedQuests)
                completedSet.Add(q);
        }

        // Inventory counts
        if (GetField<Dictionary<string, int>>(tracker, "_inventoryCounts", NonPublicInstance) is { } invDict)
        {
            invDict.Clear();
            foreach (var (k, v) in snapshot.Inventory)
                invDict[k] = v;
        }

        // Keyring
        if (GetField<HashSet<string>>(tracker, "_keyringItemKeys", NonPublicInstance) is { } keyringSet)
        {
            keyringSet.Clear();
            foreach (var k in snapshot.Keyring)
                keyringSet.Add(k);
        }
    }

    private static void SetField(object target, string fieldName, object value, BindingFlags flags)
    {
        var field = target.GetType().GetField(fieldName, flags)
            ?? throw new InvalidOperationException(
                $"Field '{fieldName}' not found on {target.GetType().Name}. " +
                "QuestStateTracker internals may have been renamed.");
        field.SetValue(target, value);
    }

    private static T? GetField<T>(object target, string fieldName, BindingFlags flags) where T : class
    {
        var field = target.GetType().GetField(fieldName, flags)
            ?? throw new InvalidOperationException(
                $"Field '{fieldName}' not found on {target.GetType().Name}. " +
                "QuestStateTracker internals may have been renamed.");
        return field.GetValue(target) as T;
    }
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
