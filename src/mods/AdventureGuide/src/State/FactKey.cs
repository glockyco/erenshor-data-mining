namespace AdventureGuide.State;

public enum FactKind
{
    InventoryItemCount,
    UnlockItemPossessed,
    QuestActive,
    QuestCompleted,
    Scene,
    SourceState,
    TimeOfDay,
    NavSet,
    TrackerSet,
}

/// <summary>
/// Typed runtime fact identifier used by the incremental dependency engine.
/// Facts are the primary invalidation unit for derived guide views.
/// </summary>
public readonly struct FactKey : IEquatable<FactKey>
{
    public FactKind Kind { get; }
    public string Key { get; }

    public FactKey(FactKind kind, string key)
    {
        Kind = kind;
        Key = key ?? string.Empty;
    }

    public bool Equals(FactKey other) => Kind == other.Kind && Key == other.Key;

    public override bool Equals(object? obj) => obj is FactKey other && Equals(other);

    public override int GetHashCode() => ((int)Kind * 397) ^ Key.GetHashCode();

    public override string ToString() => $"{Kind}:{Key}";
}
