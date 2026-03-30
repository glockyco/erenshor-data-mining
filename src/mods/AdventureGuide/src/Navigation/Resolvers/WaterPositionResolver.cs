using AdventureGuide.Graph;
using UnityEngine;
using UnityEngine.AI;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves Water nodes to shore positions rather than the water center.
///
/// On scene load, finds the live Water component for each graph node and
/// raycasts outward from the water center to find where terrain meets the
/// water surface. All discovered shore points are cached and returned by
/// Resolve so NAV picks the one closest to the player.
/// </summary>
public sealed class WaterPositionResolver : IPositionResolver
{
    private const int DirectionCount = 36;
    private const float StepSize = 5f;
    private const float MaxSearchDistance = 500f;
    private const float HeightTolerance = 5f;
    private const float NavMeshSnapRadius = 20f;
    private const float RaycastOriginY = 500f;
    private const float RaycastMaxDistance = 600f;

    private readonly EntityGraph _graph;
    private readonly Dictionary<string, List<ResolvedPosition>> _cache = new(StringComparer.Ordinal);

    public WaterPositionResolver(EntityGraph graph)
    {
        _graph = graph;
    }

    public void OnSceneLoaded()
    {
        _cache.Clear();

        var waters = UnityEngine.Object.FindObjectsOfType<Water>();
        if (waters.Length == 0)
            return;

        foreach (var node in _graph.NodesOfType(NodeType.Water))
        {
            if (node.Scene == null || node.X is null || node.Y is null || node.Z is null)
                continue;

            var water = FindWaterByPosition(waters, node);
            if (water == null)
                continue;

            var collider = water.GetComponent<Collider>();
            if (collider == null)
                continue;

            float surfaceY = collider.bounds.max.y;
            var center = new Vector3(collider.bounds.center.x, surfaceY, collider.bounds.center.z);
            var shorePoints = FindShorePoints(center, surfaceY, node.Scene);
            if (shorePoints.Count > 0)
                _cache[node.Key] = shorePoints;
        }
    }

    public void Resolve(Node node, List<ResolvedPosition> results)
    {
        if (_cache.TryGetValue(node.Key, out var shorePoints))
        {
            results.AddRange(shorePoints);
            return;
        }

        // Fallback: use the static water position if no shore points were computed.
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            results.Add(new ResolvedPosition(new Vector3(node.X.Value, node.Y.Value, node.Z.Value), node.Scene));
    }

    private static List<ResolvedPosition> FindShorePoints(Vector3 center, float surfaceY, string scene)
    {
        var points = new List<ResolvedPosition>();

        for (int i = 0; i < DirectionCount; i++)
        {
            float angle = i * (360f / DirectionCount) * Mathf.Deg2Rad;
            var dir = new Vector3(Mathf.Cos(angle), 0f, Mathf.Sin(angle));

            for (float d = StepSize; d <= MaxSearchDistance; d += StepSize)
            {
                var origin = new Vector3(
                    center.x + dir.x * d,
                    RaycastOriginY,
                    center.z + dir.z * d);

                if (!Physics.Raycast(origin, Vector3.down, out var hit, RaycastMaxDistance))
                    continue;

                if (Mathf.Abs(hit.point.y - surfaceY) > HeightTolerance)
                    continue;

                // Found terrain at water surface level — snap to NavMesh for a
                // walkable position.
                var shorePos = NavMesh.SamplePosition(hit.point, out var navHit, NavMeshSnapRadius, NavMesh.AllAreas)
                    ? navHit.position
                    : hit.point;

                points.Add(new ResolvedPosition(shorePos, scene));
                break;
            }
        }

        return points;
    }

    private static Water? FindWaterByPosition(Water[] waters, Node node)
    {
        float bestDist = float.MaxValue;
        Water? best = null;
        var nodePos = new Vector3(node.X!.Value, node.Y!.Value, node.Z!.Value);

        for (int i = 0; i < waters.Length; i++)
        {
            float dist = Vector3.Distance(waters[i].transform.position, nodePos);
            if (dist < bestDist)
            {
                bestDist = dist;
                best = waters[i];
            }
        }

        return best;
    }
}
