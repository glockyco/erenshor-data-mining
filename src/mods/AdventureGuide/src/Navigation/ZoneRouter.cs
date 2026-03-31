using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

/// <summary>
/// Zone connectivity graph with shortest-path BFS routing.
///
/// Built from EntityGraph zone line nodes and their unlock state. Provides
/// cross-zone routing: given a current scene and a target scene, returns
/// the next-hop zone line to navigate toward.
///
/// Replaces ZoneGraph.cs, reading from EntityGraph instead of GuideData.
/// </summary>
public sealed class ZoneRouter
{
    /// <summary>Result of a route query.</summary>
    public sealed class Route
    {
        /// <summary>Zone key of the first hop (the destination zone to head toward).</summary>
        public string NextHopZoneKey { get; }

        /// <summary>Scene name of the zone line in current zone to navigate to.</summary>
        public string ZoneLineScene { get; }

        /// <summary>World position of the zone line to navigate to.</summary>
        public float X { get; }
        public float Y { get; }
        public float Z { get; }

        /// <summary>Whether the first hop is through a locked zone line.</summary>
        public bool IsLocked { get; }

        /// <summary>Full path as scene names (including start and end).</summary>
        public IReadOnlyList<string> Path { get; }

        public Route(string nextHopZoneKey, string zoneLineScene,
            float x, float y, float z, bool isLocked, IReadOnlyList<string> path)
        {
            NextHopZoneKey = nextHopZoneKey;
            ZoneLineScene = zoneLineScene;
            X = x;
            Y = y;
            Z = z;
            IsLocked = isLocked;
            Path = path;
        }
    }

    /// <summary>First locked hop on a route that otherwise exists.</summary>
    public sealed class LockedHop
    {
        public string ZoneLineKey { get; }
        public string FromScene { get; }
        public string ToScene { get; }
        public float X { get; }
        public float Y { get; }
        public float Z { get; }

        public LockedHop(string zoneLineKey, string fromScene, string toScene,
            float x, float y, float z)
        {
            ZoneLineKey = zoneLineKey;
            FromScene = fromScene;
            ToScene = toScene;
            X = x;
            Y = y;
            Z = z;
        }
    }

    private readonly EntityGraph _graph;
    private readonly UnlockEvaluator _unlocks;

    // scene -> list of (destScene, zoneLineNodeKey, accessible)
    private readonly Dictionary<string, List<ZoneEdge>> _adj = new(StringComparer.OrdinalIgnoreCase);

    // zone_key -> scene name
    private readonly Dictionary<string, string> _zoneKeyToScene = new(StringComparer.OrdinalIgnoreCase);

    private readonly struct ZoneEdge
    {
        public readonly string DestScene;
        public readonly string ZoneLineKey;
        public readonly bool Accessible;
        public readonly float X, Y, Z;

        public ZoneEdge(string destScene, string zoneLineKey, bool accessible, float x, float y, float z)
        {
            DestScene = destScene;
            ZoneLineKey = zoneLineKey;
            Accessible = accessible;
            X = x;
            Y = y;
            Z = z;
        }
    }

    public ZoneRouter(EntityGraph graph, UnlockEvaluator unlocks)
    {
        _graph = graph;
        _unlocks = unlocks;

        // Build zone_key -> scene mapping from zone nodes
        foreach (var zone in graph.NodesOfType(NodeType.Zone))
        {
            if (zone.Scene != null)
                _zoneKeyToScene[zone.Key] = zone.Scene;
        }

        Rebuild();
    }

    /// <summary>
    /// Rebuild the adjacency graph from current zone line data and unlock state.
    /// Call when tracked unlock facts change.
    /// </summary>
    public void Rebuild()
    {
        _adj.Clear();

        foreach (var zl in _graph.NodesOfType(NodeType.ZoneLine))
        {
            if (zl.Scene == null || zl.DestinationZoneKey == null)
                continue;
            if (!zl.X.HasValue || !zl.Y.HasValue || !zl.Z.HasValue)
                continue;
            if (!_zoneKeyToScene.TryGetValue(zl.DestinationZoneKey, out var destScene))
                continue;

            bool accessible = IsZoneLineAccessible(zl.Key);

            if (!_adj.TryGetValue(zl.Scene, out var edges))
            {
                edges = new List<ZoneEdge>();
                _adj[zl.Scene] = edges;
            }

            // Avoid duplicate edges to same destination — keep most permissive
            bool found = false;
            for (int i = 0; i < edges.Count; i++)
            {
                if (string.Equals(edges[i].DestScene, destScene, StringComparison.OrdinalIgnoreCase))
                {
                    if (accessible && !edges[i].Accessible)
                        edges[i] = new ZoneEdge(destScene, zl.Key, true, zl.X.Value, zl.Y.Value, zl.Z.Value);
                    found = true;
                    break;
                }
            }

            if (!found)
                edges.Add(new ZoneEdge(destScene, zl.Key, accessible, zl.X.Value, zl.Y.Value, zl.Z.Value));
        }
    }

    /// <summary>
    /// Find the best route from currentScene to targetScene.
    /// Returns null if no route exists or both are the same zone.
    /// </summary>
    public Route? FindRoute(string currentScene, string targetScene)
    {
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return null;

        // Try accessible-only path first
        var result = BFS(currentScene, targetScene, accessibleOnly: true);
        if (result == null)
            result = BFS(currentScene, targetScene, accessibleOnly: false);
        return result;
    }

    /// <summary>
    /// Find the first locked hop on the best route from currentScene to targetScene.
    /// Returns null when an accessible-only route exists or no route exists at all.
    /// </summary>
    public LockedHop? FindFirstLockedHop(string currentScene, string targetScene)
    {
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return null;

        // If a fully accessible route exists, there is no unlock dependency to show.
        if (BFS(currentScene, targetScene, accessibleOnly: true) != null)
            return null;

        var route = BFS(currentScene, targetScene, accessibleOnly: false);
        if (route == null)
            return null;

        for (int i = 0; i < route.Path.Count - 1; i++)
        {
            var edge = FindEdge(route.Path[i], route.Path[i + 1], accessibleOnly: false);
            if (edge == null || edge.Value.Accessible)
                continue;

            return new LockedHop(
                edge.Value.ZoneLineKey,
                route.Path[i],
                route.Path[i + 1],
                edge.Value.X,
                edge.Value.Y,
                edge.Value.Z);
        }

        return null;
    }

    private Route? BFS(string start, string goal, bool accessibleOnly)
    {
        var queue = new Queue<(string scene, List<string> path)>();
        var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        queue.Enqueue((start, new List<string> { start }));
        visited.Add(start);

        while (queue.Count > 0)
        {
            var (current, path) = queue.Dequeue();

            if (!_adj.TryGetValue(current, out var edges))
                continue;

            foreach (var edge in edges)
            {
                if (accessibleOnly && !edge.Accessible)
                    continue;
                if (visited.Contains(edge.DestScene))
                    continue;

                var newPath = new List<string>(path) { edge.DestScene };

                if (string.Equals(edge.DestScene, goal, StringComparison.OrdinalIgnoreCase))
                {
                    // Found the route — get the first-hop zone line from start
                    var firstHopScene = newPath[1];
                    var firstEdge = FindEdge(start, firstHopScene, accessibleOnly);
                    if (firstEdge == null)
                        return null;

                    // A route from the fallback (accessibleOnly=false) pass is locked
                    // if any hop is inaccessible. The first hop is the only one we
                    // know for certain here, but any fallback route implies at least
                    // one locked hop — we would have returned from the accessible-only
                    // pass otherwise.
                    bool locked = !accessibleOnly || !firstEdge.Value.Accessible;
                    var destZoneKey = _graph.GetNode(firstEdge.Value.ZoneLineKey)?.DestinationZoneKey ?? "";
                    return new Route(destZoneKey, start,
                        firstEdge.Value.X, firstEdge.Value.Y, firstEdge.Value.Z,
                        locked, newPath);
                }

                visited.Add(edge.DestScene);
                queue.Enqueue((edge.DestScene, newPath));
            }
        }

        return null;
    }

    private ZoneEdge? FindEdge(string fromScene, string toScene, bool accessibleOnly)
    {
        if (!_adj.TryGetValue(fromScene, out var edges))
            return null;

        foreach (var edge in edges)
        {
            if (string.Equals(edge.DestScene, toScene, StringComparison.OrdinalIgnoreCase))
            {
                if (!accessibleOnly || edge.Accessible)
                    return edge;
            }
        }
        return null;
    }

    /// <summary>
    /// Check zone line accessibility via the shared incoming-unlock evaluator.
    /// </summary>
    private bool IsZoneLineAccessible(string zoneLineKey)
    {
        var node = _graph.GetNode(zoneLineKey);
        if (node == null || !node.IsEnabled)
            return false;

        return _unlocks.Evaluate(node).IsUnlocked;
    }
}
