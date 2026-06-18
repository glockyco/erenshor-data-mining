using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

/// <summary>
/// Zone connectivity graph with shortest-path routing.
///
/// Built from zone line data, respects quest-gated accessibility.
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

    private readonly GuideData _data;
    private readonly QuestStateTracker _state;

    // scene -> set of (dest_scene, dest_zone_key, accessible)
    private readonly Dictionary<string, List<(string destScene, string destZoneKey, bool accessible)>> _adj = new();

    // zone_key -> scene name
    private readonly Dictionary<string, string> _zoneKeyToScene = new(StringComparer.OrdinalIgnoreCase);

    public ZoneGraph(GuideData data, QuestStateTracker state)
    {
        _data = data;
        _state = state;

        foreach (var kvp in data.ZoneLookup)
            _zoneKeyToScene[kvp.Value.StableKey] = kvp.Key;

        Rebuild();
    }

    /// <summary>
    /// Rebuild the adjacency graph from current zone line data and quest state.
    /// Call when quest completion state changes (new zone lines become accessible).
    /// </summary>
    public void Rebuild()
    {
        _adj.Clear();

        foreach (var zl in _data.ZoneLines)
        {
            if (string.IsNullOrEmpty(zl.DestinationZoneKey))
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
                if (string.Equals(edges[i].destScene, destScene, StringComparison.OrdinalIgnoreCase))
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

    private bool IsZoneLineAccessible(ZoneLineEntry zl)
    {
        if (zl.IsEnabled && (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0))
            return true;

        if (zl.RequiredQuestGroups == null || zl.RequiredQuestGroups.Count == 0)
            return zl.IsEnabled;

        foreach (var group in zl.RequiredQuestGroups)
        {
            if (group.TrueForAll(q => _state.IsCompleted(q)))
                return true;
        }
        return false;
    }
}
