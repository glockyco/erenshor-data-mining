namespace AdventureGuide.Resolution;

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
    public ResolvedNodeContext GoalNode { get; }
    public ResolvedNodeContext TargetNode { get; }
    public string PrimaryText { get; }
    public string TargetIdentityText { get; }
    public string? ZoneText { get; }
    public string? SecondaryText { get; }
    public string? TertiaryText { get; }

    public NavigationExplanation(
        NavigationGoalKind goalKind,
        NavigationTargetKind targetKind,
        ResolvedNodeContext goalNode,
        ResolvedNodeContext targetNode,
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
