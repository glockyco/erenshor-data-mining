using UnityEngine;
using AdventureGuide.Graph;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves a Zone node to world positions by finding zone lines that
/// connect TO this zone from the current scene. Uses incoming
/// connects_zones edges filtered to zone lines in the current scene.
/// </summary>
public sealed class ZonePositionResolver : IPositionResolver
{
    private readonly EntityGraph _graph;

    public ZonePositionResolver(EntityGraph graph)
    {
        _graph = graph;
    }

    public void Resolve(Node node, List<ResolvedPosition> results)
    {
        var currentScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        int startCount = results.Count;

        // Find zone lines that connect to this zone
        foreach (var edge in _graph.InEdges(node.Key, EdgeType.ConnectsZones))
        {
            var zoneLine = _graph.GetNode(edge.Source);
            if (zoneLine == null) continue;
            if (!zoneLine.X.HasValue || !zoneLine.Y.HasValue || !zoneLine.Z.HasValue) continue;

            // Only include zone lines in the current scene — the player
            // needs to walk to one to reach the target zone
            if (string.Equals(zoneLine.Scene, currentScene, System.StringComparison.OrdinalIgnoreCase))
            {
                results.Add(new ResolvedPosition(
                    new Vector3(zoneLine.X.Value, zoneLine.Y.Value, zoneLine.Z.Value),
                    zoneLine.Scene));
            }
        }

        // If no zone lines in the current scene, include all zone lines
        // (cross-zone routing will handle it)
        if (results.Count == startCount)
        {
            foreach (var edge in _graph.InEdges(node.Key, EdgeType.ConnectsZones))
            {
                var zoneLine = _graph.GetNode(edge.Source);
                if (zoneLine == null) continue;
                if (!zoneLine.X.HasValue || !zoneLine.Y.HasValue || !zoneLine.Z.HasValue) continue;

                results.Add(new ResolvedPosition(
                    new Vector3(zoneLine.X.Value, zoneLine.Y.Value, zoneLine.Z.Value),
                    zoneLine.Scene));
            }
        }
    }
}
