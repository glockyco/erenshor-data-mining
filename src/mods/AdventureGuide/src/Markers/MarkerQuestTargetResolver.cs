using AdventureGuide.Plan;
using AdventureGuide.Resolution;

namespace AdventureGuide.Markers;

/// <summary>
/// Resolves compiled active-marker targets for a quest DB name.
/// </summary>
public sealed class MarkerQuestTargetResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly EffectiveFrontier _frontier;
    private readonly SourceResolver _sourceResolver;

    public MarkerQuestTargetResolver(
        CompiledGuide.CompiledGuide guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver)
    {
        _guide = guide;
        _frontier = frontier;
        _sourceResolver = sourceResolver;
    }

    public IReadOnlyList<ResolvedTarget> Resolve(string questDbName, string currentScene)
    {
        int questIndex = FindQuestIndexByDbName(questDbName)
            ?? throw new InvalidOperationException(
                $"Compiled guide does not contain quest DB name '{questDbName}'.");

        var frontier = new List<FrontierEntry>();
        _frontier.Resolve(questIndex, frontier, -1);

        var results = new List<ResolvedTarget>();
        for (int i = 0; i < frontier.Count; i++)
            results.AddRange(_sourceResolver.ResolveTargets(frontier[i], currentScene));
        return results;
    }

    private int? FindQuestIndexByDbName(string questDbName)
    {
        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            int nodeId = _guide.QuestNodeId(questIndex);
            uint dbNameOffset = _guide.GetNode(nodeId).DbNameOffset;
            if (dbNameOffset == 0)
                continue;
            if (string.Equals(_guide.GetString(dbNameOffset), questDbName, StringComparison.OrdinalIgnoreCase))
                return questIndex;
        }

        return null;
    }
}
