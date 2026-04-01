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
    private readonly Dictionary<string, ResolvedPosition[]> _cache = new(StringComparer.Ordinal);
    private readonly List<ResolvedPosition> _scratch = new();

    public SourcePositionCache(PositionResolverRegistry registry)
    {
        _registry = registry;
    }

    /// <summary>
    /// Resolve positions for a source node key. Returns cached results on
    /// subsequent calls for the same key. The underlying
    /// <see cref="PositionResolverRegistry"/> is called only on cache miss.
    /// </summary>
    public ResolvedPosition[] Resolve(string nodeKey)
    {
        if (_cache.TryGetValue(nodeKey, out var cached))
            return cached;

        _scratch.Clear();
        _registry.Resolve(nodeKey, _scratch);

        var result = new ResolvedPosition[_scratch.Count];
        for (int i = 0; i < _scratch.Count; i++)
            result[i] = _scratch[i];

        _cache[nodeKey] = result;
        return result;
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
