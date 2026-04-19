namespace AdventureGuide.Resolution;

/// <summary>
/// Marker-facing projection of a resolved semantic action.
/// MarkerProjector uses the same projected instruction for both text and icon
/// selection, then preserves its priority when multiple quests compete for one
/// world target.
/// </summary>
public sealed class MarkerInstruction
{
    public QuestMarkerKind Kind { get; }
    public string SubText { get; }
    public int Priority { get; }

    public MarkerInstruction(QuestMarkerKind kind, string subText, int priority)
    {
        Kind = kind;
        SubText = subText;
        Priority = priority;
    }
}
