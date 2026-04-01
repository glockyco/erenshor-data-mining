using AdventureGuide.Markers;

namespace AdventureGuide.Resolution;

/// <summary>
/// Marker-facing projection of a resolved semantic action.
/// MarkerComputer uses the same projected instruction for both text and icon
/// selection, then preserves its priority when multiple quests compete for one
/// world target.
/// </summary>
public sealed class MarkerInstruction
{
    public MarkerType Type { get; }
    public string SubText { get; }
    public int Priority { get; }

    public MarkerInstruction(MarkerType type, string subText, int priority)
    {
        Type = type;
        SubText = subText;
        Priority = priority;
    }
}
