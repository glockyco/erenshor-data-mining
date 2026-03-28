using UnityEngine;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

/// <summary>
/// Per-frame navigation driver. Resolves all entries in the <see cref="NavigationSet"/>
/// to world positions, picks the closest one to the player, and handles cross-zone
/// routing via <see cref="ZoneRouter"/> when targets are in other zones.
///
/// Quest keys are expanded via <see cref="QuestViewBuilder"/> + <see cref="FrontierComputer"/>
/// to their actionable frontier nodes before resolution.
/// </summary>
public sealed class NavigationEngine
{
    private readonly NavigationSet _navSet;
    private readonly PositionResolverRegistry _registry;
    private readonly EntityGraph _graph;
    private readonly QuestViewBuilder _viewBuilder;
    private readonly GameState _state;
    private readonly ZoneRouter _router;

    // Reusable buffers to avoid per-frame allocation.
    private readonly List<(string nodeKey, Vector3 position, string? scene)> _candidates = new();

    // Cross-zone route cache: route doesn't change within a scene.
    private string? _cachedRouteFrom;
    private string? _cachedRouteTo;
    private ZoneRouter.Route? _cachedRoute;

    /// <summary>World position of the closest resolved target, or null if nothing is resolvable.</summary>
    public Vector3? TargetPosition { get; private set; }

    /// <summary>
    /// Effective navigation target — either the direct target or a zone line
    /// waypoint when the target is in another zone. This is what the arrow
    /// and ground path should point at.
    /// </summary>
    public Vector3? EffectiveTarget { get; private set; }

    /// <summary>Node key of the closest resolved target, or null.</summary>
    public string? TargetNodeKey { get; private set; }

    /// <summary>Display name of the current target for the arrow label.</summary>
    public string? TargetDisplayName { get; private set; }

    /// <summary>True when a target position is available.</summary>
    public bool HasTarget => EffectiveTarget.HasValue;

    /// <summary>Distance from player to effective target.</summary>
    public float Distance { get; private set; }

    /// <summary>Current scene name, set by OnSceneChanged.</summary>
    public string CurrentScene { get; private set; } = "";

    public NavigationEngine(
        NavigationSet navSet,
        PositionResolverRegistry registry,
        EntityGraph graph,
        QuestViewBuilder viewBuilder,
        GameState state,
        ZoneRouter router)
    {
        _navSet = navSet;
        _registry = registry;
        _graph = graph;
        _viewBuilder = viewBuilder;
        _state = state;
        _router = router;
    }

    /// <summary>Called on scene change to update zone context.</summary>
    public void OnSceneChanged(string sceneName)
    {
        CurrentScene = sceneName;
        _cachedRouteFrom = null;
        _cachedRouteTo = null;
        _cachedRoute = null;
        _router.Rebuild();
    }

    /// <summary>
    /// Resolve all navigation-set entries and pick the closest world position to
    /// <paramref name="playerPosition"/>. Call once per frame.
    /// </summary>
    public void Update(Vector3 playerPosition)
    {
        _candidates.Clear();

        if (_navSet.Keys.Count == 0)
        {
            ClearTarget();
            return;
        }

        foreach (var key in _navSet.Keys)
            ResolveKey(key);

        if (_candidates.Count == 0)
        {
            ClearTarget();
            return;
        }

        FindClosest(playerPosition);
    }

    private void ResolveKey(string nodeKey)
    {
        var node = _graph.GetNode(nodeKey);

        // Quest nodes expand into their frontier — the set of currently-actionable steps.
        if (node != null && node.Type == NodeType.Quest)
        {
            ResolveFrontier(nodeKey);
            return;
        }

        // Non-quest (or unknown) keys resolve directly.
        var positions = _registry.Resolve(nodeKey);
        for (int i = 0; i < positions.Count; i++)
            _candidates.Add((nodeKey, positions[i].Position, positions[i].Scene));
    }

    /// <summary>
    /// Build the quest view tree, compute its frontier (actionable leaf nodes),
    /// and resolve each frontier key to world positions.
    /// </summary>
    private void ResolveFrontier(string questKey)
    {
        var viewRoot = _viewBuilder.Build(questKey);
        if (viewRoot == null)
            return;

        var frontier = FrontierComputer.ComputeFrontier(viewRoot, _state);

        foreach (var frontierKey in frontier)
        {
            var positions = _registry.Resolve(frontierKey);
            for (int i = 0; i < positions.Count; i++)
                _candidates.Add((frontierKey, positions[i].Position, positions[i].Scene));
        }
    }

    private void FindClosest(Vector3 playerPosition)
    {
        float bestSqr = float.MaxValue;
        string? bestKey = null;
        Vector3? bestPos = null;
        string? bestScene = null;

        for (int i = 0; i < _candidates.Count; i++)
        {
            var (key, pos, scene) = _candidates[i];
            // Prefer same-scene targets
            bool sameScene = string.Equals(scene, CurrentScene, StringComparison.OrdinalIgnoreCase)
                          || scene == null;
            float sqr = (pos - playerPosition).sqrMagnitude;
            // Penalize cross-zone targets so same-zone targets always win
            if (!sameScene) sqr += 1_000_000f;

            if (sqr < bestSqr)
            {
                bestSqr = sqr;
                bestKey = key;
                bestPos = pos;
                bestScene = scene;
            }
        }

        TargetPosition = bestPos;
        TargetNodeKey = bestKey;

        var targetNode = bestKey != null ? _graph.GetNode(bestKey) : null;
        TargetDisplayName = targetNode?.DisplayName;

        // Cross-zone routing: if best target is in another zone, route to zone line
        bool targetInOtherZone = bestScene != null
            && !string.Equals(bestScene, CurrentScene, StringComparison.OrdinalIgnoreCase);

        if (targetInOtherZone && bestScene != null)
        {
            var route = FindRouteCached(CurrentScene, bestScene);
            if (route != null)
            {
                EffectiveTarget = new Vector3(route.X, route.Y, route.Z);
                Distance = bestPos.HasValue
                    ? Vector3.Distance(playerPosition, EffectiveTarget.Value)
                    : 0f;
                // Append zone routing info to display name
                TargetDisplayName = targetNode?.DisplayName != null
                    ? $"{targetNode.DisplayName} (via zone line)"
                    : "Zone line";
                return;
            }
        }

        // Same-zone target or no route — navigate directly
        EffectiveTarget = bestPos;
        Distance = bestPos.HasValue
            ? Vector3.Distance(playerPosition, bestPos.Value)
            : 0f;
    }

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
        TargetPosition = null;
        EffectiveTarget = null;
        TargetNodeKey = null;
        TargetDisplayName = null;
        Distance = 0f;
    }
}
