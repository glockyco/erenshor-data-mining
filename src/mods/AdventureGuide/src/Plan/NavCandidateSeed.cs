namespace AdventureGuide.Plan;

/// <summary>
/// Seed candidate for navigation projection. NAV later resolves these into
/// positions and selects the closest actionable candidate across active NAVs.
/// </summary>
public sealed class NavCandidateSeed
{
    public PlanNodeId GoalId { get; }
    public FrontierRef Frontier { get; }

    public NavCandidateSeed(PlanNodeId goalId, FrontierRef frontier)
    {
        GoalId = goalId;
        Frontier = frontier;
    }
}