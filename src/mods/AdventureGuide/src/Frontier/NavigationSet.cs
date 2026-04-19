namespace AdventureGuide.Frontier;

/// <summary>
/// The player's selected navigation targets — a set of node keys.
/// Any navigable node can be in the set (quests, characters, items,
/// mining nodes, etc.). Click = override (clear + add single),
/// Shift+click = toggle (add/remove without affecting others).
/// </summary>
public sealed class NavigationSet : AdventureGuide.State.INavigationSetFactSource
{
    private readonly HashSet<string> _keys = new();
    private bool _factPending;

    /// <summary>Fired after the selected navigation target set changes.</summary>
    public event Action? Changed;

    /// <summary>Number of targets in the set.</summary>
    public int Count => _keys.Count;

    /// <summary>True when the set has at least one target.</summary>
    public bool HasTargets => _keys.Count > 0;

    /// <summary>The current set of node keys.</summary>
    public IReadOnlyCollection<string> Keys => _keys;

    /// <summary>Override: clear the set and add a single target (click).</summary>
    public void Override(string nodeKey)
    {
        _keys.Clear();
        _keys.Add(nodeKey);
        MarkChanged();
    }

    /// <summary>Toggle: add if absent, remove if present (shift+click).</summary>
    public void Toggle(string nodeKey)
    {
        if (!_keys.Remove(nodeKey))
            _keys.Add(nodeKey);
        MarkChanged();
    }

    /// <summary>Check whether a node is in the navigation set.</summary>
    public bool Contains(string nodeKey) => _keys.Contains(nodeKey);

    /// <summary>Remove all targets.</summary>
    public void Clear()
    {
        if (_keys.Count == 0)
            return;

        _keys.Clear();
        MarkChanged();
    }

    /// <summary>Replace contents with the given keys. Used for persistence restore.</summary>
    public void Load(IEnumerable<string> keys)
    {
        _keys.Clear();
        foreach (var key in keys)
            _keys.Add(key);
        MarkChanged();
    }

    /// <summary>
    /// Monotonically increasing version for change detection.
    /// Consumers compare against their snapshot to know if the set changed.
    /// </summary>
    public int Version { get; private set; }

    /// <summary>Drains the pending fact emission caused by membership changes
    /// since the last drain. Returns <c>FactKey(NavSet, "*")</c> once per change
    /// batch, empty otherwise. Plugin's update loop drains once per frame and
    /// feeds the result into <c>Engine.InvalidateFacts</c> so queries that read
    /// the nav set via <c>GuideReader.ReadNavSetKeys</c> invalidate correctly.</summary>
    public IReadOnlyCollection<AdventureGuide.State.FactKey> DrainPendingFacts()
    {
        if (!_factPending)
            return Array.Empty<AdventureGuide.State.FactKey>();
        _factPending = false;
        return new[] { new AdventureGuide.State.FactKey(AdventureGuide.State.FactKind.NavSet, "*") };
    }

    private void MarkChanged()
    {
        Version++;
        _factPending = true;
        Changed?.Invoke();
    }
}
