using UnityEngine;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

/// <summary>
/// Two-phase navigation driver.
///
/// <b>Resolve phase</b> (on state change): builds view trees, computes frontiers,
/// resolves positions via <see cref="PositionResolverRegistry"/>, picks the best
/// target. Runs when <see cref="NavigationSet.Version"/> or
/// <see cref="QuestStateTracker.Version"/> changes, or on scene change.
///
/// <b>Track phase</b> (per frame): updates the target's live position from
/// <see cref="EntityRegistry"/> for smooth NPC tracking, computes distance
/// and handles cross-zone routing. O(1) per frame, zero allocations.
/// </summary>
public sealed class NavigationEngine
{
    private readonly NavigationSet _navSet;
    private readonly PositionResolverRegistry _registry;
    private readonly EntityGraph _graph;
    private readonly QuestViewBuilder _viewBuilder;
    private readonly GameState _gameState;
    private readonly QuestStateTracker _tracker;
    private readonly ZoneRouter _router;
    private readonly EntityRegistry _entities;

    // Reusable buffers — owned by the engine, never exposed.
    private readonly List<(string nodeKey, Vector3 position, string? scene, Views.ViewNode? viewNode, string? sourceKey)> _candidates = new();
    private readonly List<ResolvedPosition> _positionBuffer = new();

    // ── Resolved target state (set by Resolve, read by Track) ────────

    /// <summary>Node key of the resolved target, or null if no target.</summary>
    public string? TargetNodeKey { get; private set; }

    /// <summary>Static/resolved position of the target (from graph data).</summary>
    public Vector3? TargetPosition { get; private set; }

    /// <summary>Scene the target is in (from resolver).</summary>
    public string? TargetScene { get; private set; }

    /// <summary>
    /// Effective position the arrow should point at. For same-zone targets,
    /// this is the live NPC position (updated per-frame). For cross-zone targets,
    /// this is the zone line waypoint position.
    /// </summary>
    public Vector3? EffectiveTarget { get; private set; }

    /// <summary>Display name shown on the arrow label.</summary>
    public string? TargetDisplayName { get; private set; }

    /// <summary>True when navigation has a valid target.</summary>
    public bool HasTarget => EffectiveTarget.HasValue;

    /// <summary>Distance from player to effective target.</summary>
    public float Distance { get; private set; }

    /// <summary>Current scene name.</summary>
    public string CurrentScene { get; private set; } = "";

    // ── Change detection ─────────────────────────────────────────────

    private int _lastNavSetVersion = -1;
    private int _lastTrackerVersion = -1;
    private string _lastResolveScene = "";

    // ── Cross-zone route cache ───────────────────────────────────────

    private string? _cachedRouteFrom;
    private string? _cachedRouteTo;
    private ZoneRouter.Route? _cachedRoute;

    public NavigationEngine(
        NavigationSet navSet,
        PositionResolverRegistry registry,
        EntityGraph graph,
        QuestViewBuilder viewBuilder,
        GameState gameState,
        QuestStateTracker tracker,
        ZoneRouter router,
        EntityRegistry entities)
    {
        _navSet = navSet;
        _registry = registry;
        _graph = graph;
        _viewBuilder = viewBuilder;
        _gameState = gameState;
        _tracker = tracker;
        _router = router;
        _entities = entities;
    }

    /// <summary>Called on scene change to update zone context and force re-resolve.</summary>
    public void OnSceneChanged(string sceneName)
    {
        CurrentScene = sceneName;
        _cachedRouteFrom = null;
        _cachedRouteTo = null;
        _cachedRoute = null;
        _router.Rebuild();
        // Force re-resolve on next Update
        _lastResolveScene = "";
    }

    /// <summary>
    /// Call once per frame. Runs the resolve phase if state changed,
    /// then runs the track phase for live position updates.
    /// </summary>
    public void Update(Vector3 playerPosition)
    {
        if (_navSet.Keys.Count == 0)
        {
            ClearTarget();
            return;
        }

        // Phase 1: Resolve — only when something changed
        bool navChanged = _navSet.Version != _lastNavSetVersion;
        bool stateChanged = _tracker.Version != _lastTrackerVersion;
        bool sceneChanged = !string.Equals(CurrentScene, _lastResolveScene,
            StringComparison.OrdinalIgnoreCase);

        if (navChanged || stateChanged || sceneChanged)
        {
            _lastNavSetVersion = _navSet.Version;
            _lastTrackerVersion = _tracker.Version;
            _lastResolveScene = CurrentScene;
            Resolve(playerPosition);
        }

        // Phase 2: Track — every frame, cheap
        Track(playerPosition);
    }

    // ── Phase 1: Resolve ─────────────────────────────────────────────

    /// <summary>
    /// Full resolution: expand quest frontiers, resolve all positions,
    /// pick the closest candidate. Called only on state change.
    /// </summary>
    private void Resolve(Vector3 playerPosition)
    {
        _candidates.Clear();

        foreach (var key in _navSet.Keys)
            ResolveKey(key);

        if (_candidates.Count == 0)
        {
            ClearTarget();
            return;
        }

        PickClosest(playerPosition);
    }

    private void ResolveKey(string nodeKey)
    {
        var node = _graph.GetNode(nodeKey);

        // Quest nodes expand into their frontier.
        if (node != null && node.Type == NodeType.Quest)
        {
            ResolveFrontier(nodeKey);
            return;
        }

        // Non-quest keys resolve directly.
        _positionBuffer.Clear();
        _registry.Resolve(nodeKey, _positionBuffer);
        for (int i = 0; i < _positionBuffer.Count; i++)
            _candidates.Add((nodeKey, _positionBuffer[i].Position, _positionBuffer[i].Scene, null, _positionBuffer[i].SourceKey));
    }

    private void ResolveFrontier(string questKey)
    {
        var viewRoot = _viewBuilder.Build(questKey);
        if (viewRoot == null) return;

        var frontier = FrontierComputer.ComputeFrontier(viewRoot, _gameState);

        for (int i = 0; i < frontier.Count; i++)
        {
            var viewNode = frontier[i];
            _positionBuffer.Clear();
            _registry.Resolve(viewNode.NodeKey, _positionBuffer);
            for (int j = 0; j < _positionBuffer.Count; j++)
                _candidates.Add((viewNode.NodeKey, _positionBuffer[j].Position, _positionBuffer[j].Scene, viewNode, _positionBuffer[j].SourceKey));
        }
    }

    private void PickClosest(Vector3 playerPosition)
    {
        float bestSqr = float.MaxValue;
        string? bestKey = null;
        Vector3? bestPos = null;
        string? bestScene = null;
        Views.ViewNode? bestViewNode = null;
        string? bestSourceKey = null;

        for (int i = 0; i < _candidates.Count; i++)
        {
            var (key, pos, scene, viewNode, sourceKey) = _candidates[i];
            bool sameScene = string.Equals(scene, CurrentScene, StringComparison.OrdinalIgnoreCase)
                          || scene == null;
            float sqr = (pos - playerPosition).sqrMagnitude;
            // Same-scene targets always win over cross-zone
            if (!sameScene) sqr += 1_000_000f;

            if (sqr < bestSqr)
            {
                bestSqr = sqr;
                bestKey = key;
                bestPos = pos;
                bestScene = scene;
                bestViewNode = viewNode;
                bestSourceKey = sourceKey;
            }
        }

        TargetNodeKey = bestKey;
        TargetPosition = bestPos;
        TargetScene = bestScene;

        // Format display name with action text when frontier context is available
        if (bestViewNode != null)
            TargetDisplayName = Frontier.ActionTextFormatter.FormatSummary(bestViewNode, _tracker);
        else
        {
            var targetNode = bestKey != null ? _graph.GetNode(bestKey) : null;
            TargetDisplayName = targetNode?.DisplayName;
        }

        // Cross-zone routing: resolve zone line waypoint
        bool targetInOtherZone = bestScene != null
            && !string.Equals(bestScene, CurrentScene, StringComparison.OrdinalIgnoreCase);

        if (targetInOtherZone)
        {
            var route = FindRouteCached(CurrentScene, bestScene!);
            if (route != null)
            {
                EffectiveTarget = new Vector3(route.X, route.Y, route.Z);
                if (TargetDisplayName != null)
                    TargetDisplayName += " (via zone line)";
                else
                    TargetDisplayName = "Zone line";
            }
            else
            {
                EffectiveTarget = bestPos;
            }
        }
        else
        {
            EffectiveTarget = bestPos;
        }

        // Append requirement text when target spawn is quest-gated
        if (bestSourceKey != null)
        {
            var gatedEdges = _graph.OutEdges(bestSourceKey, EdgeType.GatedByQuest);
            for (int i = 0; i < gatedEdges.Count; i++)
            {
                var gatingQuest = _graph.GetNode(gatedEdges[i].Target);
                if (gatingQuest?.DbName != null && !_tracker.IsCompleted(gatingQuest.DbName))
                {
                    TargetDisplayName = TargetDisplayName != null
                        ? $"{TargetDisplayName}\nRequires: {gatingQuest.DisplayName}"
                        : $"Requires: {gatingQuest.DisplayName}";
                    break; // Only show first unmet requirement
                }
            }
        }
    }

    // ── Phase 2: Track ───────────────────────────────────────────────

    /// <summary>
    /// Per-frame live tracking. Updates the effective target position from
    /// live NPC transforms when the target is a character in the current scene.
    /// Computes distance for display.
    /// </summary>
    private void Track(Vector3 playerPosition)
    {
        if (TargetNodeKey == null || !TargetPosition.HasValue)
        {
            Distance = 0f;
            return;
        }

        // For same-scene character targets, track the live NPC position
        bool isSameScene = string.Equals(TargetScene, CurrentScene,
            StringComparison.OrdinalIgnoreCase) || TargetScene == null;

        if (isSameScene)
        {
            var targetNode = _graph.GetNode(TargetNodeKey);
            if (targetNode != null && targetNode.Type == NodeType.Character)
            {
                var liveNPC = _entities.FindClosest(TargetNodeKey, playerPosition);
                if (liveNPC != null)
                {
                    var livePos = liveNPC.transform.position;
                    EffectiveTarget = livePos;
                }
                // If NPC is dead, EffectiveTarget stays at the static/spawn position
                // set during Resolve. Future: fall back to shortest respawn timer.
            }
        }

        // Update distance
        Distance = EffectiveTarget.HasValue
            ? Vector3.Distance(playerPosition, EffectiveTarget.Value)
            : 0f;
    }

    // ── Helpers ───────────────────────────────────────────────────────

    private ZoneRouter.Route? FindRouteCached(string from, string to)
    {
        if (from == _cachedRouteFrom && to == _cachedRouteTo)
            return _cachedRoute;
        _cachedRouteFrom = from;
        _cachedRouteTo = to;
        _cachedRoute = _router.FindRoute(from, to);
        return _cachedRoute;
    }

    private void ClearTarget()
    {
        TargetNodeKey = null;
        TargetPosition = null;
        TargetScene = null;
        EffectiveTarget = null;
        TargetDisplayName = null;
        Distance = 0f;
    }
}
