namespace AdventureGuide.State;

public enum GuideFactKind
{
	InventoryItemCount,
	UnlockItemPossessed,
	QuestActive,
	QuestCompleted,
	Scene,
	SourceState,
	TimeOfDay,
}

/// <summary>
/// Typed runtime fact identifier used by the incremental dependency engine.
/// Facts are the primary invalidation unit for derived guide views.
/// </summary>
public readonly struct GuideFactKey : IEquatable<GuideFactKey>
{
    public GuideFactKind Kind { get; }
    public string Key { get; }

    public GuideFactKey(GuideFactKind kind, string key)
    {
        Kind = kind;
        Key = key ?? string.Empty;
    }

    public bool Equals(GuideFactKey other) => Kind == other.Kind && Key == other.Key;
    public override bool Equals(object? obj) => obj is GuideFactKey other && Equals(other);
    public override int GetHashCode() => ((int)Kind * 397) ^ Key.GetHashCode();
    public override string ToString() => $"{Kind}:{Key}";
}
