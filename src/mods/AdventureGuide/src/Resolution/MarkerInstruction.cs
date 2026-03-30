using AdventureGuide.Navigation;

namespace AdventureGuide.Resolution;

/// <summary>
/// Marker-facing projection of a resolved quest target.
/// Marker generation does not re-derive quest semantics; it renders this model.
/// </summary>
public sealed class MarkerInstruction
{
    public MarkerType Type { get; }
    public string SubText { get; }

    public MarkerInstruction(MarkerType type, string subText)
    {
        Type = type;
        SubText = subText;
    }
}
