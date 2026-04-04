namespace AdventureGuide.Graph;

public enum MarkerInteractionKind
{
    TalkTo,
    SayKeyword,
}

/// <summary>
/// Immutable interaction descriptor used by marker blueprints.
/// </summary>
public readonly struct MarkerInteraction
{
    public MarkerInteractionKind Kind { get; }
    public string? Keyword { get; }

    public MarkerInteraction(MarkerInteractionKind kind, string? keyword)
    {
        Kind = kind;
        Keyword = keyword;
    }
}
