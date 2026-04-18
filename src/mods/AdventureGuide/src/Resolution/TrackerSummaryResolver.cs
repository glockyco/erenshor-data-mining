using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Plan;
using AdventureGuide.State;

namespace AdventureGuide.Resolution;

public sealed class TrackerSummaryResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly QuestResolutionService _questResolutionService;
    private readonly DiagnosticsCore? _diagnostics;
    private string? _lastResolveQuestKey;
    private bool _lastResolveUsedPreferredTarget;
    private string? _lastSummaryText;

    internal TrackerSummaryResolver(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        QuestResolutionService questResolutionService,
        DiagnosticsCore? diagnostics = null
    )
    {
        _guide = guide;
        _phases = phases;
        _questResolutionService = questResolutionService;
        _diagnostics = diagnostics;
    }

    public TrackerSummary? Resolve(
        string questKey,
        string? questDbName,
        string currentScene = "",
        ResolvedQuestTarget? preferredTarget = null,
        QuestStateTracker? tracker = null
    )
    {
        var token = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.TrackerSummaryResolve,
            DiagnosticsContext.Root(DiagnosticTrigger.Unknown),
            primaryKey: questKey
        );
        long startTick = Stopwatch.GetTimestamp();
        try
        {
            _lastResolveQuestKey = questKey;
            if (preferredTarget != null && tracker != null)
            {
                var preferredSummary = BuildPreferredTargetSummary(preferredTarget, tracker);
                Remember(preferredSummary, usedPreferredTarget: true);
                return preferredSummary;
            }
            if (string.IsNullOrEmpty(questDbName))
            {
                Remember(null, usedPreferredTarget: false);
                return null;
            }

            var questNode = _guide.GetQuestByDbName(questDbName);
            if (questNode == null)
            {
                Remember(null, usedPreferredTarget: false);
                return null;
            }

            var record = _questResolutionService.ResolveQuest(questNode.Key, currentScene);
            var targets = record.CompiledTargets;
            if (targets.Count > 0)
            {
                var target = SelectBestTarget(targets);
                var goalNode = BuildGoalContext(target);
                var targetNode = new ResolvedNodeContext(
                    _guide.GetNodeKey(target.TargetNodeId),
                    _guide.GetNode(target.TargetNodeId)
                );
                var explanation = NavigationExplanationBuilder.Build(
                    target.Semantic,
                    goalNode,
                    targetNode
                );
                string? requiredForContext = null;
                if (target.RequiredForQuestIndex >= 0)
                {
                    requiredForContext =
                        $"Needed for: {_guide.GetDisplayName(_guide.QuestNodeId(target.RequiredForQuestIndex))}";
                }
                var summary = new TrackerSummary(
                    explanation.PrimaryText,
                    target.Semantic.RationaleText,
                    requiredForContext
                );
                Remember(summary, usedPreferredTarget: false);
                return summary;
            }

            if (record.Frontier.Count == 0)
            {
                Remember(null, usedPreferredTarget: false);
                return null;
            }

            var fallback = TrackerSummaryBuilder.Build(_guide, _phases, record.Frontier[0]);
            Remember(fallback, usedPreferredTarget: false);
            return fallback;
        }
        finally
        {
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    Stopwatch.GetTimestamp() - startTick,
                    value0: _lastResolveUsedPreferredTarget ? 1 : 0,
                    value1: _lastSummaryText != null ? 1 : 0
                );
        }
    }

    private TrackerSummary BuildPreferredTargetSummary(
        ResolvedQuestTarget target,
        QuestStateTracker tracker
    )
    {
        string? prerequisiteQuestName = null;
        if (
            !string.IsNullOrEmpty(target.RequiredForQuestKey)
            && _guide.TryGetNodeId(target.RequiredForQuestKey, out int requiredQuestNodeId)
        )
        {
            prerequisiteQuestName = _guide.GetDisplayName(requiredQuestNodeId);
        }

        return NavigationExplanationBuilder.BuildTrackerSummary(
            target.GoalNode,
            target.Semantic,
            tracker,
            additionalCount: 0,
            prerequisiteQuestName
        );
    }

    private static ResolvedTarget SelectBestTarget(IReadOnlyList<ResolvedTarget> targets)
    {
        var best = targets[0];
        for (int i = 1; i < targets.Count; i++)
        {
            if (targets[i].AvailabilityPriority < best.AvailabilityPriority)
                best = targets[i];
        }

        return best;
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

    internal TrackerDiagnosticsSnapshot ExportDiagnosticsSnapshot()
    {
        return new TrackerDiagnosticsSnapshot(
            trackedQuestCount: 0,
            lastResolveQuestKey: _lastResolveQuestKey,
            lastResolveUsedPreferredTarget: _lastResolveUsedPreferredTarget,
            lastSummaryText: _lastSummaryText
        );
    }

    private void Remember(TrackerSummary? summary, bool usedPreferredTarget)
    {
        _lastResolveUsedPreferredTarget = usedPreferredTarget;
        _lastSummaryText = summary?.PrimaryText;
    }
}
