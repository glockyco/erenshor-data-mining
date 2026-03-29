using AdventureGuide.Views;

namespace AdventureGuide.Frontier;

/// <summary>
/// The player's selected navigation targets — a set of node keys.
///
/// Any navigable node can be in the set (quests, characters, items,
/// mining nodes, etc.).  Click = override (clear + add single),
/// Shift+click = toggle (add/remove without affecting others).
/// </summary>
public sealed class NavigationSet
{
    private readonly HashSet<string> _keys = new();
    private readonly Dictionary<string, ViewNode> _contexts = new(StringComparer.Ordinal);

    /// <summary>Number of targets in the set.</summary>
    public int Count => _keys.Count;

    /// <summary>True when the set has at least one target.</summary>
    public bool HasTargets => _keys.Count > 0;

    /// <summary>The current set of node keys.</summary>
    public IReadOnlyCollection<string> Keys => _keys;

    /// <summary>Override: clear the set and add a single target (click).</summary>
    public void Override(string nodeKey, ViewNode? context = null)
    {
        _keys.Clear();
        _contexts.Clear();
        _keys.Add(nodeKey);
        if (context != null)
            _contexts[nodeKey] = CloneViewNode(context);
        Version++;
    }

    /// <summary>Toggle: add if absent, remove if present (shift+click).</summary>
    public void Toggle(string nodeKey, ViewNode? context = null)
    {
        if (_keys.Remove(nodeKey))
        {
            _contexts.Remove(nodeKey);
        }
        else
        {
            _keys.Add(nodeKey);
            if (context != null)
                _contexts[nodeKey] = CloneViewNode(context);
        }
        Version++;
    }

    /// <summary>Check whether a node is in the navigation set.</summary>
    public bool Contains(string nodeKey) => _keys.Contains(nodeKey);

    /// <summary>Try to get the contextual pruned view node for a manual target.</summary>
    public bool TryGetContext(string nodeKey, out ViewNode? context)
    {
        if (_contexts.TryGetValue(nodeKey, out var stored))
        {
            context = CloneViewNode(stored);
            return true;
        }
        context = null;
        return false;
    }

    /// <summary>Remove all targets.</summary>
    public void Clear()
    {
        if (_keys.Count == 0 && _contexts.Count == 0) return;
        _keys.Clear();
        _contexts.Clear();
        Version++;
    }

    /// <summary>Replace contents with the given keys. Used for persistence restore.</summary>
    public void Load(IEnumerable<string> keys)
    {
        _keys.Clear();
        _contexts.Clear();
        foreach (var key in keys)
            _keys.Add(key);
        Version++;
    }

    /// <summary>
    /// Monotonically increasing version for change detection.
    /// Consumers compare against their snapshot to know if the set changed.
    /// </summary>
    public int Version { get; private set; }

    private static ViewNode CloneViewNode(ViewNode source)
    {
        var clone = new ViewNode(source.NodeKey, source.Node, source.EdgeType, source.Edge)
        {
            IsCycleRef = source.IsCycleRef,
            DefaultExpanded = source.DefaultExpanded,
            EffectiveLevel = source.EffectiveLevel,
        };

        if (source.SourceZones != null)
            clone.SourceZones = new List<string>(source.SourceZones);
        if (source.UnlockDependency != null)
            clone.UnlockDependency = CloneViewNode(source.UnlockDependency);

        for (int i = 0; i < source.Children.Count; i++)
            clone.Children.Add(CloneViewNode(source.Children[i]));

        return clone;
    }
}
