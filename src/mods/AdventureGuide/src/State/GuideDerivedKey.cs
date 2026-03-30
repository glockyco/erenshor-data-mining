namespace AdventureGuide.State;

public enum GuideDerivedKind
{
    QuestStructure,
    QuestTargets,
}

/// <summary>
/// Identifier for a maintained derived guide view.
/// </summary>
public readonly struct GuideDerivedKey : IEquatable<GuideDerivedKey>
{
    public GuideDerivedKind Kind { get; }
    public string Key { get; }

    public GuideDerivedKey(GuideDerivedKind kind, string key)
    {
        Kind = kind;
        Key = key ?? string.Empty;
    }

    public bool Equals(GuideDerivedKey other) => Kind == other.Kind && Key == other.Key;
    public override bool Equals(object? obj) => obj is GuideDerivedKey other && Equals(other);
    public override int GetHashCode() => ((int)Kind * 397) ^ Key.GetHashCode();
    public override string ToString() => $"{Kind}:{Key}";
}
