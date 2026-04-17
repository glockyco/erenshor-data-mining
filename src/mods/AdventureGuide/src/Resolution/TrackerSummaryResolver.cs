using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

public sealed class TrackerSummaryResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly EffectiveFrontier _frontier;
    private readonly SourceResolver _sourceResolver;

    public TrackerSummaryResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver)
    {
        _guide = guide;
        _phases = phases;
        _frontier = frontier;
        _sourceResolver = sourceResolver;
    }

    public TrackerSummary? Resolve(string questKey, string? questDbName, string currentScene = "")
    {
        if (string.IsNullOrEmpty(questDbName))
            return null;

        var questNode = _guide.GetQuestByDbName(questDbName);
        if (questNode == null || !_guide.TryGetNodeId(questNode.Key, out int nodeId))
            return null;

        int questIndex = _guide.FindQuestIndex(nodeId);
        if (questIndex < 0)
            return null;

        var frontier = new List<FrontierEntry>();
        _frontier.Resolve(questIndex, frontier, -1);
        if (frontier.Count == 0)
            return null;

        for (int i = 0; i < frontier.Count; i++)
        {
            var targets = _sourceResolver.ResolveTargets(frontier[i], currentScene);
            if (targets.Count == 0)
                continue;

            var target = targets[0];
            var goalNode = BuildGoalContext(target);
            var targetNode = new ResolvedNodeContext(_guide.GetNodeKey(target.TargetNodeId), _guide.GetNode(target.TargetNodeId));
            var explanation = NavigationExplanationBuilder.Build(target.Semantic, goalNode, targetNode);
            string? requiredForContext = null;
            if (target.RequiredForQuestIndex >= 0)
                requiredForContext = $"Needed for: {_guide.GetDisplayName(_guide.QuestNodeId(target.RequiredForQuestIndex))}";
            return new TrackerSummary(explanation.PrimaryText, target.Semantic.RationaleText, requiredForContext);
        }

        return TrackerSummaryBuilder.Build(_guide, _phases, frontier[0]);
    }

    private ResolvedNodeContext BuildGoalContext(ResolvedTarget target)
    {
        if (!string.IsNullOrEmpty(target.Semantic.GoalNodeKey))
        {
            var goalNode = _guide.GetNode(target.Semantic.GoalNodeKey);
            if (goalNode != null)
                return new ResolvedNodeContext(target.Semantic.GoalNodeKey, goalNode);
        }

        string targetNodeKey = _guide.GetNodeKey(target.TargetNodeId);
        return new ResolvedNodeContext(targetNodeKey, _guide.GetNode(target.TargetNodeId));
    }
}
