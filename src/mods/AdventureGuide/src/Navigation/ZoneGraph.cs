using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

/// <summary>A reachable placement's approach route and its required final entry.</summary>
public readonly struct PlacementRoute
{
    public ZoneGraph.Route? Route { get; }
    public ZoneLineEntry? EntryLine { get; }

    public PlacementRoute(ZoneGraph.Route? route, ZoneLineEntry? entryLine)
    {
        Route = route;
        EntryLine = entryLine;
    }
}

/// <summary>
/// Zone connectivity graph with shortest-path routing.
///
/// Built from zone line data, respects gate accessibility.
/// Provides BFS shortest path from any zone to any other zone,
/// first through accessible routes, then through the full graph
/// (including locked) when no accessible path exists.
/// </summary>
public sealed class ZoneGraph
{
    /// <summary>Result of a route query.</summary>
    public sealed class Route
    {
        /// <summary>Zone key of the first hop (the zone line destination to navigate to).</summary>
        public string NextHopZoneKey { get; }

        /// <summary>Whether the first hop is through a locked zone line.</summary>
        public bool IsLocked { get; }

        /// <summary>Full path as scene names (including start and end).</summary>
        public IReadOnlyList<string> Path { get; }

        public Route(string nextHopZoneKey, bool isLocked, IReadOnlyList<string> path)
        {
            NextHopZoneKey = nextHopZoneKey;
            IsLocked = isLocked;
            Path = path;
        }
    }

    /// <summary>Routes from one scene, scoped to a single requirement resolution.</summary>
    public sealed class RouteLookup
    {
        private sealed class Node
        {
            public readonly string Scene;
            public readonly Node? Parent;
            public readonly int Hops;
            public readonly string NextHopZoneKey;
            public readonly bool FirstHopLocked;
            public Route? Route;

            public Node(string scene, Node? parent, string nextHopZoneKey, bool firstHopLocked)
            {
                Scene = scene;
                Parent = parent;
                Hops = parent == null ? 0 : parent.Hops + 1;
                NextHopZoneKey = nextHopZoneKey;
                FirstHopLocked = firstHopLocked;
            }
        }

        private readonly ZoneGraph _graph;
        private readonly Dictionary<string, Node> _accessible = new(
            StringComparer.OrdinalIgnoreCase
        );
        private readonly Dictionary<string, Node> _full = new(StringComparer.OrdinalIgnoreCase);

        public string Scene { get; }

        internal RouteLookup(ZoneGraph graph, string scene)
        {
            _graph = graph;
            Scene = scene;
            var root = new Node(scene, null, "", false);
            _accessible.Add(scene, root);
            _full.Add(scene, root);
            var queue = new Queue<(Node node, bool accessibleOnly)>();
            queue.Enqueue((root, true));
            queue.Enqueue((root, false));
            while (queue.Count > 0)
            {
                var (node, accessibleOnly) = queue.Dequeue();
                if (!graph._adj.TryGetValue(node.Scene, out var edges))
                    continue;
                var visited = accessibleOnly ? _accessible : _full;
                foreach (var (destination, zoneKey, accessible) in edges)
                {
                    if ((accessibleOnly && !accessible) || visited.ContainsKey(destination))
                        continue;
                    var next = new Node(
                        destination,
                        node,
                        node.Hops == 0 ? zoneKey : node.NextHopZoneKey,
                        node.Hops == 0 ? !accessible : node.FirstHopLocked
                    );
                    visited.Add(destination, next);
                    queue.Enqueue((next, accessibleOnly));
                }
            }
        }

        private Node? FindNode(string scene) =>
            _accessible.TryGetValue(scene, out var accessible) ? accessible
            : _full.TryGetValue(scene, out var full) ? full
            : null;

        public int HopCount(string scene) => FindNode(scene)?.Hops ?? int.MaxValue;

        public Route? FindRoute(string scene)
        {
            var node = FindNode(scene);
            if (node == null || node.Hops == 0)
                return null;
            if (node.Route != null)
                return node.Route;
            var path = new string[node.Hops + 1];
            for (Node? current = node; current != null; current = current.Parent)
                path[current.Hops] = current.Scene;
            node.Route = new Route(node.NextHopZoneKey, node.FirstHopLocked, path);
            return node.Route;
        }

        public PlacementRoute? GetPlacementRoute(AdventureGuide.Data.SpawnPoint spawn) =>
            _graph.GetPlacementRoute(spawn, Scene, this);
    }

    public RouteLookup BuildRouteLookup(string scene) => new(this, scene);

    private readonly GuideData _data;
    private readonly GateConditions _gates;

    // scene -> set of (dest_scene, dest_zone_key, accessible)
    private readonly Dictionary<
        string,
        List<(string destScene, string destZoneKey, bool accessible)>
    > _adj = new();

    // zone_key -> scene name
    private readonly Dictionary<string, string> _zoneKeyToScene = new(
        StringComparer.OrdinalIgnoreCase
    );

    public ZoneGraph(GuideData data, GateConditions gates)
    {
        _data = data;
        _gates = gates;

        foreach (var kvp in data.ZoneLookup)
            _zoneKeyToScene[kvp.Value.StableKey] = kvp.Key;

        Rebuild();
    }

    /// <summary>
    /// Rebuild the adjacency graph from current zone line data and gate facts.
    /// Call when guide state changes.
    /// Every NPC death and inventory change calls it, so it refills the edge
    /// lists in place instead of allocating a new graph.
    /// </summary>
    public void Rebuild()
    {
        foreach (var existing in _adj.Values)
            existing.Clear();

        var zoneLines = _data.ZoneLines;
        for (int line = 0; line < zoneLines.Count; line++)
        {
            var zl = zoneLines[line];
            if (string.IsNullOrEmpty(zl.DestinationZoneKey))
                continue;
            if (!_gates.CanBecomeAvailable(zl.Condition))
                continue;

            if (!_zoneKeyToScene.TryGetValue(zl.DestinationZoneKey, out var destScene))
                continue;

            bool accessible = IsZoneLineAccessible(zl);

            if (!_adj.TryGetValue(zl.Scene, out var edges))
            {
                edges = new List<(string, string, bool)>();
                _adj[zl.Scene] = edges;
            }

            // Avoid duplicate edges (multiple zone lines to same destination)
            bool found = false;
            for (int i = 0; i < edges.Count; i++)
            {
                if (
                    string.Equals(edges[i].destScene, destScene, StringComparison.OrdinalIgnoreCase)
                )
                {
                    // Keep the most permissive: if any zone line to this dest is accessible, the edge is accessible
                    if (accessible && !edges[i].accessible)
                        edges[i] = (destScene, zl.DestinationZoneKey, true);
                    found = true;
                    break;
                }
            }

            if (!found)
                edges.Add((destScene, zl.DestinationZoneKey, accessible));
        }
    }

    /// <summary>
    /// Find the best route from currentScene to targetScene.
    /// Returns null if no route exists even through locked zone lines.
    /// </summary>
    public Route? FindRoute(string currentScene, string targetScene)
    {
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return null; // same zone, no routing needed

        // 1. Try accessible-only path
        var accessiblePath = BFS(currentScene, targetScene, accessibleOnly: true);
        if (accessiblePath != null)
        {
            var nextScene = accessiblePath[1];
            var nextZoneKey = FindZoneKeyForEdge(currentScene, nextScene, accessibleOnly: true);
            return new Route(nextZoneKey!, isLocked: false, accessiblePath);
        }

        // 2. Fall back to full graph (including locked)
        var fullPath = BFS(currentScene, targetScene, accessibleOnly: false);
        if (fullPath != null)
        {
            var nextScene = fullPath[1];
            var nextZoneKey = FindZoneKeyForEdge(currentScene, nextScene, accessibleOnly: false);
            // The first hop is locked if there's no accessible edge to it
            bool firstHopLocked = !HasAccessibleEdge(currentScene, nextScene);
            return new Route(nextZoneKey!, isLocked: firstHopLocked, fullPath);
        }

        return null;
    }

    /// <summary>Route to a placement through its cheapest usable entry, preserving entry order on ties.</summary>
    public PlacementRoute? GetPlacementRoute(AdventureGuide.Data.SpawnPoint spawn, string scene) =>
        GetPlacementRoute(spawn, scene, null);

    private PlacementRoute? GetPlacementRoute(
        AdventureGuide.Data.SpawnPoint spawn,
        string scene,
        RouteLookup? routes
    )
    {
        if (string.Equals(scene, spawn.Scene, StringComparison.OrdinalIgnoreCase))
            return new PlacementRoute(null, null);
        if (spawn.Entries == null)
        {
            var route =
                routes == null ? FindRoute(scene, spawn.Scene) : routes.FindRoute(spawn.Scene);
            return route == null ? null : new PlacementRoute(route, null);
        }

        ZoneLineEntry? bestEntry = null;
        Route? bestRoute = null;
        int bestHops = int.MaxValue;
        foreach (int index in spawn.Entries)
        {
            var entry = _data.ZoneLines[index];
            if (!_gates.CanBecomeAvailable(entry.Condition))
                continue;
            bool sameScene = string.Equals(scene, entry.Scene, StringComparison.OrdinalIgnoreCase);
            var route = routes == null && !sameScene ? FindRoute(scene, entry.Scene) : null;
            int hops = sameScene
                ? 0
                : routes?.HopCount(entry.Scene)
                    ?? (route == null ? int.MaxValue : route.Path.Count - 1);
            if (hops < bestHops)
            {
                bestEntry = entry;
                bestRoute = route;
                bestHops = hops;
            }
        }
        if (bestEntry == null)
            return null;
        var approach = routes == null ? bestRoute : routes.FindRoute(bestEntry.Scene);
        return new PlacementRoute(approach, bestEntry);
    }

    /// <summary>All physical lines for a route hop, preserving guide order.</summary>
    internal IEnumerable<ZoneLineEntry> LinesForHop(string fromScene, string toScene)
    {
        foreach (var line in _data.ZoneLines)
            if (
                string.Equals(line.Scene, fromScene, StringComparison.OrdinalIgnoreCase)
                && _zoneKeyToScene.TryGetValue(line.DestinationZoneKey, out var destination)
                && string.Equals(destination, toScene, StringComparison.OrdinalIgnoreCase)
            )
                yield return line;
    }

    private List<string>? BFS(string start, string goal, bool accessibleOnly)
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

            foreach (var (destScene, _, accessible) in edges)
            {
                if (accessibleOnly && !accessible)
                    continue;
                if (visited.Contains(destScene))
                    continue;

                var newPath = new List<string>(path) { destScene };

                if (string.Equals(destScene, goal, StringComparison.OrdinalIgnoreCase))
                    return newPath;

                visited.Add(destScene);
                queue.Enqueue((destScene, newPath));
            }
        }

        return null;
    }

    private string? FindZoneKeyForEdge(string fromScene, string toScene, bool accessibleOnly)
    {
        if (!_adj.TryGetValue(fromScene, out var edges))
            return null;

        foreach (var (destScene, destZoneKey, accessible) in edges)
        {
            if (string.Equals(destScene, toScene, StringComparison.OrdinalIgnoreCase))
            {
                if (!accessibleOnly || accessible)
                    return destZoneKey;
            }
        }
        return null;
    }

    private bool HasAccessibleEdge(string fromScene, string toScene)
    {
        if (!_adj.TryGetValue(fromScene, out var edges))
            return false;

        foreach (var (destScene, _, accessible) in edges)
        {
            if (accessible && string.Equals(destScene, toScene, StringComparison.OrdinalIgnoreCase))
                return true;
        }
        return false;
    }

    private bool IsZoneLineAccessible(ZoneLineEntry zl) => _gates.IsAvailable(zl.Condition);
}
