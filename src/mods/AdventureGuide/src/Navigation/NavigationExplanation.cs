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
/// Semantic explanation of why navigation points at the current target.
///
/// This separates navigation meaning from rendering. Arrow, tracker, and any
/// future consumers should render this model rather than reconstructing meaning
/// from raw nodes or ad hoc strings.
/// </summary>
public sealed class NavigationExplanation
{
    public NavigationGoalKind GoalKind { get; }
    public NavigationTargetKind TargetKind { get; }

    /// <summary>The branch/requested node that produced this navigation target.</summary>
    public ViewNode GoalNode { get; }

    /// <summary>The immediate actionable node whose position won candidate selection.</summary>
    public ViewNode TargetNode { get; }

    /// <summary>Primary user-facing goal text, e.g. "Collect Rune of The Hills".</summary>
    public string GoalText { get; }

    /// <summary>Immediate target text, e.g. "Ghost of Wyland Sercher".</summary>
    public string TargetText { get; }

    /// <summary>Zone/area label for the immediate target when known.</summary>
    public string? ZoneText { get; }

    /// <summary>Optional reason/progress line, e.g. "Drops the required item".</summary>
    public string? DetailText { get; }

    public NavigationExplanation(
        NavigationGoalKind goalKind,
        NavigationTargetKind targetKind,
        ViewNode goalNode,
        ViewNode targetNode,
        string goalText,
        string targetText,
        string? zoneText,
        string? detailText)
    {
        GoalKind = goalKind;
        TargetKind = targetKind;
        GoalNode = goalNode;
        TargetNode = targetNode;
        GoalText = goalText;
        TargetText = targetText;
        ZoneText = zoneText;
        DetailText = detailText;
    }
}

/// <summary>
/// Compact tracker projection derived from <see cref="NavigationExplanation"/>.
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
