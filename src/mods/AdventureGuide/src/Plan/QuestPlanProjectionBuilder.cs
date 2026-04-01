using AdventureGuide.State;

namespace AdventureGuide.Plan;

/// <summary>
/// Builds shared frontier/tracker/nav projections from a canonical quest plan.
/// Later migrations can enrich these projections without changing consumers' use
/// of the service-layer handoff type.
/// </summary>
public static class QuestPlanProjectionBuilder
{
    public static QuestPlanProjection Build(QuestPlan plan, GameState state)
    {
        var frontier = FrontierResolver.ComputeFrontier(plan, state);
        var tracker = new TrackerProjection(frontier);

        var navSeeds = new List<NavCandidateSeed>(frontier.Count);
        for (int i = 0; i < frontier.Count; i++)
            navSeeds.Add(new NavCandidateSeed(frontier[i].GoalId, frontier[i]));

        return new QuestPlanProjection(plan, frontier, tracker, navSeeds);
    }
}