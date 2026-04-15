using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Resolves tracker summaries through the compiled frontier path.
/// </summary>
public sealed class TrackerSummaryResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly EffectiveFrontier _frontier;
    public TrackerSummaryResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        EffectiveFrontier frontier)
    {
        _guide = guide;
        _phases = phases;
        _frontier = frontier;
    }

    public TrackerSummary? Resolve(string questKey, string? questDbName)
    {
        if (string.IsNullOrEmpty(questDbName))
        {
            return null;
        }

        var questNode = _guide.GetQuestByDbName(questDbName);
        if (questNode == null || !_guide.TryGetNodeId(questNode.Key, out int nodeId))
        {
            return null;
        }

        int questIndex = _guide.FindQuestIndex(nodeId);
        if (questIndex < 0)
        {
            return null;
        }

        var frontier = new List<FrontierEntry>();
        _frontier.Resolve(questIndex, frontier, -1);
        if (frontier.Count == 0)
        {
            return null;
        }

        return TrackerSummaryBuilder.Build(_guide, _phases, frontier[0]);
    }
}
