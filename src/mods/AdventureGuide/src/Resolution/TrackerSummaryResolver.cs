using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Resolves tracker summaries through the compiled frontier path when available,
/// with an optional legacy fallback during the runtime cutover.
/// </summary>
public sealed class TrackerSummaryResolver
{
    private readonly CompiledGuide.CompiledGuide? _guide;
    private readonly QuestPhaseTracker? _phases;
    private readonly EffectiveFrontier? _frontier;
    private readonly Func<string, TrackerSummary?>? _legacyResolver;

    public TrackerSummaryResolver(
        CompiledGuide.CompiledGuide? guide,
        QuestPhaseTracker? phases,
        EffectiveFrontier? frontier,
        Func<string, TrackerSummary?>? legacyResolver)
    {
        _guide = guide;
        _phases = phases;
        _frontier = frontier;
        _legacyResolver = legacyResolver;
    }

    public TrackerSummary? Resolve(string questKey, string? questDbName)
    {
        if (_guide != null && _phases != null && _frontier != null && !string.IsNullOrEmpty(questDbName))
        {
            int? questIndex = FindQuestIndexByDbName(questDbName);
            if (questIndex != null)
            {
                var frontier = new List<FrontierEntry>();
                _frontier.Resolve(questIndex.Value, frontier, -1);
                if (frontier.Count > 0)
                    return TrackerSummaryBuilder.Build(_guide, _phases, frontier[0]);
            }
        }

        return _legacyResolver?.Invoke(questKey);
    }

    private int? FindQuestIndexByDbName(string dbName)
    {
        if (_guide == null)
            return null;

        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            int nodeId = _guide.QuestNodeId(questIndex);
            uint dbNameOffset = _guide.GetNode(nodeId).DbNameOffset;
            if (dbNameOffset == 0)
                continue;
            if (string.Equals(_guide.GetString(dbNameOffset), dbName, StringComparison.OrdinalIgnoreCase))
                return questIndex;
        }

        return null;
    }
}
