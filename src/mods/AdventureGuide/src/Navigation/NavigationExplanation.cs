using AdventureGuide.Views;

namespace AdventureGuide.Navigation;

public enum NavigationGoalKind
{
    Generic,
    StartQuest,
    CompleteQuest,
    CollectItem,
    KillTarget,
    ReadItem,
    TalkToTarget,
    TravelToZone,
    CompleteBlockingQuest,
    UnlockRoute,
}

public enum NavigationTargetKind
{
    Unknown,
    Character,
    Enemy,
    Item,
    Quest,
    Zone,
    ZoneLine,
    Object,
}

/// <summary>
/// Arrow-facing projection of a resolved semantic action.
/// Navigation keeps the underlying goal/target nodes for debugging and tie-breaks,
/// but rendering consumes already-projected arrow lines rather than rebuilding
/// wording from raw graph/view state.
/// </summary>
public sealed class NavigationExplanation
{
    public NavigationGoalKind GoalKind { get; }
    public NavigationTargetKind TargetKind { get; }
    public ViewNode GoalNode { get; }
    public ViewNode TargetNode { get; }
    public string PrimaryText { get; }
    public string TargetIdentityText { get; }
    public string? ZoneText { get; }
    public string? SecondaryText { get; }
    public string? TertiaryText { get; }

    public NavigationExplanation(
        NavigationGoalKind goalKind,
        NavigationTargetKind targetKind,
        ViewNode goalNode,
        ViewNode targetNode,
        string primaryText,
        string targetIdentityText,
        string? zoneText,
        string? secondaryText,
        string? tertiaryText)
    {
        GoalKind = goalKind;
        TargetKind = targetKind;
        GoalNode = goalNode;
        TargetNode = targetNode;
        PrimaryText = primaryText;
        TargetIdentityText = targetIdentityText;
        ZoneText = zoneText;
        SecondaryText = secondaryText;
        TertiaryText = tertiaryText;
    }
}

/// <summary>
/// Compact tracker projection derived from the shared resolved action semantics.
/// Tracker is intentionally lossy compared to the arrow: it is an overview of
/// all tracked quests, not a single immediate instruction surface.
/// </summary>
public readonly struct TrackerSummary
{
    public readonly string PrimaryText;
    public readonly string? SecondaryText;

    public TrackerSummary(string primaryText, string? secondaryText)
    {
        PrimaryText = primaryText;
        SecondaryText = secondaryText;
    }
}
