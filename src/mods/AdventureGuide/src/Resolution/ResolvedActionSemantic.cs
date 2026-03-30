using AdventureGuide.Navigation;

namespace AdventureGuide.Resolution;

/// <summary>
/// Shared player-facing meaning for one resolved target interpretation.
///
/// This is intentionally surface-agnostic: markers, tracker rows, and arrow
/// labels project different subsets of the same semantic action instead of
/// rebuilding wording from traversal artifacts.
/// </summary>
public sealed class ResolvedActionSemantic
{
    public NavigationGoalKind GoalKind { get; }
    public NavigationTargetKind TargetKind { get; }
    public ResolvedActionKind ActionKind { get; }
    public string? GoalNodeKey { get; }
    public int? GoalQuantity { get; }
    public string? KeywordText { get; }
    public string? PayloadText { get; }
    public string TargetIdentityText { get; }
    public string? ContextText { get; }
    public string? RationaleText { get; }
    public string? ZoneText { get; }
    public string? AvailabilityText { get; }
    public MarkerType PreferredMarkerType { get; }
    public int MarkerPriority { get; }

    public ResolvedActionSemantic(
        NavigationGoalKind goalKind,
        NavigationTargetKind targetKind,
        ResolvedActionKind actionKind,
        string? goalNodeKey,
        int? goalQuantity,
        string? keywordText,
        string? payloadText,
        string targetIdentityText,
        string? contextText,
        string? rationaleText,
        string? zoneText,
        string? availabilityText,
        MarkerType preferredMarkerType,
        int markerPriority)
    {
        GoalKind = goalKind;
        TargetKind = targetKind;
        ActionKind = actionKind;
        GoalNodeKey = goalNodeKey;
        GoalQuantity = goalQuantity;
        KeywordText = keywordText;
        PayloadText = payloadText;
        TargetIdentityText = targetIdentityText;
        ContextText = contextText;
        RationaleText = rationaleText;
        ZoneText = zoneText;
        AvailabilityText = availabilityText;
        PreferredMarkerType = preferredMarkerType;
        MarkerPriority = markerPriority;
    }
}

public enum ResolvedActionKind
{
    Unknown,
    Talk,
    SayKeyword,
    ShoutKeyword,
    Kill,
    Read,
    Travel,
    Fish,
    Mine,
    Collect,
    Buy,
    Give,
    CompleteQuest,
}
