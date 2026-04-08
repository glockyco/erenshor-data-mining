using AdventureGuide.Graph;
using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Bridges mixed NavigationSet inputs during the compiled-guide cutover.
/// Quest keys resolve through the compiled frontier/source pipeline, while
/// non-quest keys can temporarily reuse the legacy navigation resolver.
/// </summary>
public sealed class NavigationTargetResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly EffectiveFrontier _frontier;
    private readonly SourceResolver _sourceResolver;
    private readonly Func<string, IReadOnlyList<ResolvedQuestTarget>> _legacyResolver;

    public NavigationTargetResolver(
        CompiledGuide.CompiledGuide guide,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        Func<string, IReadOnlyList<ResolvedQuestTarget>> legacyResolver)
    {
        _guide = guide;
        _frontier = frontier;
        _sourceResolver = sourceResolver;
        _legacyResolver = legacyResolver;
    }

    public IReadOnlyList<ResolvedTarget> Resolve(string nodeKey, string currentScene)
    {
        if (string.IsNullOrWhiteSpace(nodeKey))
            return Array.Empty<ResolvedTarget>();

        if (_guide.TryGetNodeId(nodeKey, out int nodeId)
            && _guide.GetNode(nodeId).NodeType == (byte)NodeType.Quest)
        {
            int questIndex = FindQuestIndex(nodeId);
            if (questIndex < 0)
                return Array.Empty<ResolvedTarget>();

            var frontier = new List<FrontierEntry>();
            _frontier.Resolve(questIndex, frontier, -1);

            var results = new List<ResolvedTarget>();
            for (int i = 0; i < frontier.Count; i++)
                results.AddRange(_sourceResolver.ResolveTargets(frontier[i], currentScene));
            return results;
        }

        return ConvertLegacyTargets(_legacyResolver(nodeKey));
    }

    private IReadOnlyList<ResolvedTarget> ConvertLegacyTargets(
        IReadOnlyList<ResolvedQuestTarget> legacyTargets)
    {
        if (legacyTargets.Count == 0)
            return Array.Empty<ResolvedTarget>();

        var results = new List<ResolvedTarget>(legacyTargets.Count);
        for (int i = 0; i < legacyTargets.Count; i++)
        {
            if (TryConvertLegacyTarget(legacyTargets[i], out var target))
                results.Add(target);
        }

        return results;
    }

    private bool TryConvertLegacyTarget(
        ResolvedQuestTarget legacyTarget,
        out ResolvedTarget target)
    {
        target = default;

        if (!_guide.TryGetNodeId(legacyTarget.TargetNodeKey, out int targetNodeId))
            return false;

        int positionNodeId;
        if (!string.IsNullOrEmpty(legacyTarget.SourceKey)
            && _guide.TryGetNodeId(legacyTarget.SourceKey, out int sourceNodeId))
        {
            positionNodeId = sourceNodeId;
        }
        else
        {
            positionNodeId = targetNodeId;
        }

        int requiredForQuestIndex = -1;
        if (!string.IsNullOrEmpty(legacyTarget.RequiredForQuestKey)
            && _guide.TryGetNodeId(legacyTarget.RequiredForQuestKey, out int requiredQuestNodeId))
        {
            requiredForQuestIndex = FindQuestIndex(requiredQuestNodeId);
        }

        target = new ResolvedTarget(
            targetNodeId,
            positionNodeId,
            MapRole(legacyTarget.Semantic.PreferredMarkerKind),
            legacyTarget.Semantic,
            legacyTarget.X,
            legacyTarget.Y,
            legacyTarget.Z,
            legacyTarget.Scene,
            isLive: false,
            legacyTarget.IsActionable,
            questIndex: -1,
            requiredForQuestIndex);
        return true;
    }

    private ResolvedTargetRole MapRole(QuestMarkerKind markerKind) =>
        markerKind switch
        {
            QuestMarkerKind.QuestGiver or QuestMarkerKind.QuestGiverRepeat or QuestMarkerKind.QuestGiverBlocked
                => ResolvedTargetRole.Giver,
            QuestMarkerKind.TurnInPending or QuestMarkerKind.TurnInReady or QuestMarkerKind.TurnInRepeatReady
                => ResolvedTargetRole.TurnIn,
            _ => ResolvedTargetRole.Objective,
        };

    private int FindQuestIndex(int questNodeId)
    {
        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            if (_guide.QuestNodeId(questIndex) == questNodeId)
                return questIndex;
        }

        return -1;
    }
}
