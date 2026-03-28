using UnityEngine;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

/// <summary>
/// Per-frame navigation driver. Resolves all entries in the <see cref="NavigationSet"/>
/// to world positions and picks the closest one to the player.
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

    // Reusable buffer to avoid per-frame allocation.
    private readonly List<(string nodeKey, Vector3 position)> _candidates = new();

    /// <summary>World position of the closest resolved target, or null if nothing is resolvable.</summary>
    public Vector3? TargetPosition { get; private set; }

    /// <summary>Node key of the closest resolved target, or null.</summary>
    public string? TargetNodeKey { get; private set; }

    /// <summary>True when a target position is available.</summary>
    public bool HasTarget => TargetPosition.HasValue;

    public NavigationEngine(
        NavigationSet navSet,
        PositionResolverRegistry registry,
        EntityGraph graph,
        QuestViewBuilder viewBuilder,
        GameState state)
    {
        _navSet = navSet;
        _registry = registry;
        _graph = graph;
        _viewBuilder = viewBuilder;
        _state = state;
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
        AddPositions(nodeKey, _registry.Resolve(nodeKey));
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
            AddPositions(frontierKey, _registry.Resolve(frontierKey));
    }

    private void AddPositions(string nodeKey, List<Vector3> positions)
    {
        for (int i = 0; i < positions.Count; i++)
            _candidates.Add((nodeKey, positions[i]));
    }

    private void FindClosest(Vector3 playerPosition)
    {
        float bestSqr = float.MaxValue;
        string? bestKey = null;
        Vector3? bestPos = null;

        for (int i = 0; i < _candidates.Count; i++)
        {
            var (key, pos) = _candidates[i];
            float sqr = (pos - playerPosition).sqrMagnitude;
            if (sqr < bestSqr)
            {
                bestSqr = sqr;
                bestKey = key;
                bestPos = pos;
            }
        }

        TargetPosition = bestPos;
        TargetNodeKey = bestKey;
    }

    private void ClearTarget()
    {
        TargetPosition = null;
        TargetNodeKey = null;
    }
}
