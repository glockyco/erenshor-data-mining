using AdventureGuide.Graph;
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
    private readonly Dictionary<string, EntityViewNode> _contexts = new(StringComparer.Ordinal);

    /// <summary>Fired after the selected navigation target set changes.</summary>
    public event Action? Changed;

    /// <summary>Number of targets in the set.</summary>
    public int Count => _keys.Count;

    /// <summary>True when the set has at least one target.</summary>
    public bool HasTargets => _keys.Count > 0;

    /// <summary>The current set of node keys.</summary>
    public IReadOnlyCollection<string> Keys => _keys;

    /// <summary>Override: clear the set and add a single target (click).</summary>
    public void Override(string nodeKey, EntityViewNode? context = null)
    {
        _keys.Clear();
        _contexts.Clear();
        _keys.Add(nodeKey);
        if (context != null)
            _contexts[nodeKey] = (EntityViewNode)CloneViewNode(context);
        MarkChanged();
    }

    /// <summary>Toggle: add if absent, remove if present (shift+click).</summary>
    public void Toggle(string nodeKey, EntityViewNode? context = null)
    {
        if (_keys.Remove(nodeKey))
        {
            _contexts.Remove(nodeKey);
        }
        else
        {
            _keys.Add(nodeKey);
            if (context != null)
                _contexts[nodeKey] = (EntityViewNode)CloneViewNode(context);
        }
        MarkChanged();
    }

    /// <summary>Check whether a node is in the navigation set.</summary>
    public bool Contains(string nodeKey) => _keys.Contains(nodeKey);

    /// <summary>Try to get the contextual pruned view node for a manual target.</summary>
    public bool TryGetContext(string nodeKey, out EntityViewNode? context)
    {
        if (_contexts.TryGetValue(nodeKey, out var stored))
        {
            context = (EntityViewNode)CloneViewNode(stored);
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
        MarkChanged();
    }

    /// <summary>Replace contents with the given keys. Used for persistence restore.</summary>
    public void Load(IEnumerable<string> keys)
    {
        _keys.Clear();
        _contexts.Clear();
        foreach (var key in keys)
            _keys.Add(key);
        MarkChanged();
    }

    /// <summary>
    /// Monotonically increasing version for change detection.
    /// Consumers compare against their snapshot to know if the set changed.
    /// </summary>
    public int Version { get; private set; }

    private void MarkChanged()
    {
        Version++;
        Changed?.Invoke();
    }

    private static ViewNode CloneViewNode(ViewNode source)
    {
        switch (source)
        {
            case EntityViewNode ev:
            {
                var clone = new EntityViewNode(ev.NodeKey, ev.Node, ev.EdgeType, ev.Edge)
                {
                    IsCycleRef = ev.IsCycleRef,
                    DefaultExpanded = ev.DefaultExpanded,
                    EffectiveLevel = ev.EffectiveLevel,
                };
                if (ev.SourceZones != null)
                    clone.SourceZones = new List<string>(ev.SourceZones);
                if (ev.UnlockDependency != null)
                    clone.UnlockDependency = CloneViewNode(ev.UnlockDependency);
                for (int i = 0; i < ev.Children.Count; i++)
                    clone.Children.Add(CloneViewNode(ev.Children[i]));
                return clone;
            }
            case VariantGroupNode vg:
            {
                var clone = new VariantGroupNode(vg.NodeKey, vg.Label,
                    vg.EdgeType ?? EdgeType.RequiresItem)
                {
                    DefaultExpanded = vg.DefaultExpanded,
                };
                for (int i = 0; i < vg.Children.Count; i++)
                    clone.Children.Add(CloneViewNode(vg.Children[i]));
                return clone;
            }
            case UnlockGroupNode ug:
            {
                var clone = new UnlockGroupNode(ug.NodeKey, ug.Label)
                {
                    DefaultExpanded = ug.DefaultExpanded,
                };
                for (int i = 0; i < ug.Children.Count; i++)
                    clone.Children.Add(CloneViewNode(ug.Children[i]));
                return clone;
            }
            default:
                throw new InvalidOperationException($"Unknown ViewNode type: {source.GetType().Name}");
        }
    }
}
