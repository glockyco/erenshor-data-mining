namespace AdventureGuide.Plan;

/// <summary>
/// Shared canonical projection bundle derived from a <see cref="QuestPlan"/>.
/// This is the service-layer handoff point for NAV, tracker, and markers before
/// they fully migrate off the old ViewNode-based structure.
/// </summary>
public sealed class QuestPlanProjection
{
    public QuestPlan Plan { get; }
    public IReadOnlyList<FrontierRef> Frontier { get; }
    public TrackerProjection Tracker { get; }
    public IReadOnlyList<NavCandidateSeed> NavigationSeeds { get; }

    public QuestPlanProjection(
        QuestPlan plan,
        IReadOnlyList<FrontierRef> frontier,
        TrackerProjection tracker,
        IReadOnlyList<NavCandidateSeed> navigationSeeds)
    {
        Plan = plan;
        Frontier = frontier;
        Tracker = tracker;
        NavigationSeeds = navigationSeeds;
    }
}