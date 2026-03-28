using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves an Item node to world positions by walking incoming source edges
/// (drops, sells, gives, yields, rewards) and recursively following crafting
/// material chains. Each source's position is resolved via the registry.
/// </summary>
public sealed class ItemPositionResolver : IPositionResolver
{
    private readonly EntityGraph _graph;
    private readonly PositionResolverRegistry _registry;

    private static readonly EdgeType[] SourceEdgeTypes =
    {
        EdgeType.DropsItem,
        EdgeType.SellsItem,
        EdgeType.GivesItem,
        EdgeType.YieldsItem,
        EdgeType.RewardsItem,
    };

    public ItemPositionResolver(EntityGraph graph, PositionResolverRegistry registry)
    {
        _graph = graph;
        _registry = registry;
    }

    public List<Vector3> Resolve(Node node)
    {
        var result = new List<Vector3>();
        var visited = new HashSet<string>();
        CollectSourcePositions(node.Key, result, visited);
        return result;
    }

    private void CollectSourcePositions(string itemKey, List<Vector3> result, HashSet<string> visited)
    {
        if (!visited.Add(itemKey)) return;

        // Direct sources: NPCs/nodes that drop/sell/give/yield/reward this item
        foreach (var et in SourceEdgeTypes)
        {
            foreach (var edge in _graph.InEdges(itemKey, et))
                result.AddRange(_registry.Resolve(edge.Source));
        }

        // Crafting chains: item → CraftedFrom → recipe → RequiresMaterial → ingredients
        foreach (var craftEdge in _graph.OutEdges(itemKey, EdgeType.CraftedFrom))
        {
            foreach (var matEdge in _graph.OutEdges(craftEdge.Target, EdgeType.RequiresMaterial))
                CollectSourcePositions(matEdge.Target, result, visited);
        }
    }
}
