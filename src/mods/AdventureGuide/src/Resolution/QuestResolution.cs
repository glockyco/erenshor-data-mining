using AdventureGuide.Navigation;
using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Canonical resolved answer for one quest in the current runtime state.
/// Every surface renders a projection of this model instead of rebuilding its
/// own frontier, targets, or summaries.
/// </summary>
public sealed class QuestResolution
{
    public string QuestKey { get; }
    public QuestPlanProjection PlanProjection { get; }
    public IReadOnlyList<FrontierRef> Frontier => PlanProjection.Frontier;
    public IReadOnlyList<ResolvedQuestTarget> Targets { get; }
    public TrackerSummary TrackerSummary { get; }

    public QuestResolution(
        string questKey,
        QuestPlanProjection planProjection,
        IReadOnlyList<ResolvedQuestTarget> targets,
        TrackerSummary trackerSummary)
    {
        QuestKey = questKey;
        PlanProjection = planProjection;
        Targets = targets;
        TrackerSummary = trackerSummary;
    }
}