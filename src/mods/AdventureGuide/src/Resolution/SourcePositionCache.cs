using AdventureGuide.Graph;
using AdventureGuide.Position;

namespace AdventureGuide.Resolution;

/// <summary>
/// Caches resolved positions by source node key across quest resolutions.
///
/// The cache lives across resolution batches within one scene. It is cleared
/// on scene change and when a live-world change triggers a full marker rebuild.
/// Individual entries are evicted when their source-state facts change.
///
/// This is safe because target cache invalidation for live-world changes uses
/// AffectedQuestKeys from the change set, which triggers fresh BuildTargets
/// calls. Those calls re-resolve through this cache; evicted entries get
/// re-populated from the position resolvers.
/// </summary>
public sealed class SourcePositionCache
{
    private readonly PositionResolverRegistry _registry;
    private readonly EntityGraph _graph;
    private readonly Dictionary<string, ResolvedPosition[]> _cache = new(StringComparer.Ordinal);
    private readonly List<ResolvedPosition> _scratch = new();

    public SourcePositionCache(PositionResolverRegistry registry, EntityGraph graph)
    {
        _registry = registry;
        _graph = graph;
    }

    /// <summary>
    /// Resolve positions for a source node key. Returns cached results on
    /// subsequent calls for the same key. The underlying
    /// <see cref="PositionResolverRegistry"/> is called only on cache miss.
    ///
    /// Character nodes are never served from cache: their positions reflect live
    /// NPC state (spawn, death, movement) that changes independently of the
    /// scene-change signals used to clear other cached entries. Every resolution
    /// pass for a Character key gets a fresh call to the registry.
    /// </summary>
    public ResolvedPosition[] Resolve(string nodeKey)
    {
        // Character positions depend on live NPC state (spawn/death/movement) and
        // must never be served from cache. Every resolution pass gets fresh data.
        if (_graph.GetNode(nodeKey)?.Type == NodeType.Character)
        {
            _scratch.Clear();
            _registry.Resolve(nodeKey, _scratch);
            var result = new ResolvedPosition[_scratch.Count];
            for (int i = 0; i < _scratch.Count; i++) result[i] = _scratch[i];
            return result;
        }

        if (_cache.TryGetValue(nodeKey, out var cached))
            return cached;

        _scratch.Clear();
        _registry.Resolve(nodeKey, _scratch);

        var result2 = new ResolvedPosition[_scratch.Count];
        for (int i = 0; i < _scratch.Count; i++)
            result2[i] = _scratch[i];

        _cache[nodeKey] = result2;
        return result2;
    }

    /// <summary>
    /// Append resolved positions to a caller-provided list. Same caching
    /// semantics as <see cref="Resolve(string)"/>.
    /// </summary>
    public void Resolve(string nodeKey, List<ResolvedPosition> results)
    {
        var positions = Resolve(nodeKey);
        for (int i = 0; i < positions.Length; i++)
            results.Add(positions[i]);
    }

    /// <summary>Evict cached entries for specific source keys.</summary>
    public void Invalidate(IEnumerable<string> sourceKeys)
    {
        foreach (var key in sourceKeys)
            _cache.Remove(key);
    }

    /// <summary>Evict a single cached entry.</summary>
    public void Invalidate(string sourceKey) => _cache.Remove(sourceKey);

    /// <summary>Clear all cached entries.</summary>
    public void Clear() => _cache.Clear();
}
