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

        int? questIndex = FindQuestIndexByDbName(questDbName);
        if (questIndex == null)
        {
            return null;
        }

        var frontier = new List<FrontierEntry>();
        _frontier.Resolve(questIndex.Value, frontier, -1);
        if (frontier.Count == 0)
        {
            return null;
        }

        return TrackerSummaryBuilder.Build(_guide, _phases, frontier[0]);
    }

    private int? FindQuestIndexByDbName(string dbName)
    {
        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            int nodeId = _guide.QuestNodeId(questIndex);
            string? nodeDbName = _guide.GetDbName(nodeId);
            if (nodeDbName == null)
                continue;
            if (string.Equals(nodeDbName, dbName, StringComparison.OrdinalIgnoreCase))
                return questIndex;
        }

        return null;
    }
}
