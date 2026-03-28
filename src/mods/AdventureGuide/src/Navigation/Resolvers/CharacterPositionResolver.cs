using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves a Character node to world positions. Prefers the live NPC's
/// real-time position (via EntityRegistry), then falls back to static
/// coordinates on the node, then to spawn point edges in the graph.
/// </summary>
public sealed class CharacterPositionResolver : IPositionResolver
{
    private readonly EntityRegistry _entities;
    private readonly EntityGraph _graph;

    public CharacterPositionResolver(EntityRegistry entities, EntityGraph graph)
    {
        _entities = entities;
        _graph = graph;
    }

    public List<Vector3> Resolve(Node node)
    {
        // Prefer live NPC position for real-time tracking
        var playerPos = GameData.PlayerControl?.transform.position ?? Vector3.zero;
        var liveNPC = _entities.FindClosest(node.Key, playerPos);
        if (liveNPC != null)
            return new List<Vector3> { liveNPC.transform.position };

        // Fallback: static coordinates baked into the graph node
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            return new List<Vector3> { new Vector3(node.X.Value, node.Y.Value, node.Z.Value) };

        // Last resort: collect positions from linked spawn point nodes
        var result = new List<Vector3>();
        foreach (var edge in _graph.OutEdges(node.Key, EdgeType.HasSpawn))
        {
            var spawnNode = _graph.GetNode(edge.Target);
            if (spawnNode?.X != null && spawnNode.Y != null && spawnNode.Z != null)
                result.Add(new Vector3(spawnNode.X.Value, spawnNode.Y.Value, spawnNode.Z.Value));
        }
        return result;
    }
}
