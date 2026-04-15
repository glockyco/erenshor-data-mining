namespace AdventureGuide.Resolution;

/// <summary>
/// Compact tracker projection derived from the shared resolved action semantics.
/// Tracker is intentionally lossy compared to the arrow: it is an overview of
/// all tracked quests, not a single immediate instruction surface.
/// </summary>
public readonly struct TrackerSummary
{
    public readonly string PrimaryText;
    public readonly string? SecondaryText;
    public readonly string? RequiredForContext;

    public TrackerSummary(string primaryText, string? secondaryText = null, string? requiredForContext = null)
    {
        PrimaryText = primaryText;
        SecondaryText = secondaryText;
        RequiredForContext = requiredForContext;
    }
}
