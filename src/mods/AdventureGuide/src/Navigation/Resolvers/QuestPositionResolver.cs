using UnityEngine;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves a Quest node to world positions by building the quest's view tree,
/// computing its frontier (the set of actionable nodes), and resolving each
/// frontier node's position via the registry.
/// </summary>
public sealed class QuestPositionResolver : IPositionResolver
{
    private readonly QuestViewBuilder _viewBuilder;
    private readonly GameState _state;
    private readonly PositionResolverRegistry _registry;

    public QuestPositionResolver(QuestViewBuilder viewBuilder, GameState state, PositionResolverRegistry registry)
    {
        _viewBuilder = viewBuilder;
        _state = state;
        _registry = registry;
    }

    public List<Vector3> Resolve(Node node)
    {
        var root = _viewBuilder.Build(node.Key);
        if (root == null)
            return new List<Vector3>();

        var frontier = FrontierComputer.ComputeFrontier(root, _state);
        var result = new List<Vector3>();
        foreach (var key in frontier)
            result.AddRange(_registry.Resolve(key));
        return result;
    }
}
