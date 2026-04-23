using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.State;

namespace AdventureGuide.Resolution;

public sealed class TrackerSummaryResolver
{
	private readonly CompiledGuide.CompiledGuide _guide;
	private readonly QuestPhaseTracker _phases;
	private readonly GuideReader _reader;
	private readonly DiagnosticsCore? _diagnostics;
	private string? _lastResolveQuestKey;
	private bool _lastResolveUsedPreferredTarget;
	private string? _lastSummaryText;

	internal TrackerSummaryResolver(
		CompiledGuide.CompiledGuide guide,
		QuestPhaseTracker phases,
		GuideReader reader,
		DiagnosticsCore? diagnostics = null)
	{
		_guide = guide;
		_phases = phases;
		_reader = reader;
		_diagnostics = diagnostics;
	}

	/// <summary>
	/// Pre-populates the shared quest-resolution cache for the supplied tracked quest
	/// keys so per-quest resolve calls during the same frame hit memoized entries.
	/// </summary>
	public void WarmBatch(IEnumerable<string> questKeys, string currentScene)
	{
		foreach (var questKey in questKeys)
			_ = _reader.ReadQuestResolution(questKey, currentScene);
	}

	public TrackerSummary? Resolve(
		string questKey,
		string? questDbName,
		string currentScene = "",
		ResolvedQuestTarget? preferredTarget = null,
		QuestStateTracker? tracker = null)
	{
		var token = _diagnostics?.BeginSpan(
			DiagnosticSpanKind.TrackerSummaryResolve,
			DiagnosticsContext.Root(DiagnosticTrigger.Unknown),
			primaryKey: questKey);
		long startTick = Stopwatch.GetTimestamp();
		try
		{
			_lastResolveQuestKey = questKey;
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

			var record = _reader.ReadQuestResolution(questNode.Key, currentScene);
			if (preferredTarget != null && tracker != null)
			{
				var navigationTargets = record.NavigationTargets;
				if (navigationTargets.Count == 0)
				{
					var preferredSummary = BuildPreferredTargetSummary(preferredTarget, tracker);
					Remember(preferredSummary, usedPreferredTarget: true);
					return preferredSummary;
				}

				var currentPreferredTarget = FindCurrentPreferredTarget(navigationTargets, preferredTarget);
				if (currentPreferredTarget != null)
				{
					var refreshedPreferredTarget = RefreshPreferredTarget(currentPreferredTarget, preferredTarget);
					var preferredSummary = BuildPreferredTargetSummary(refreshedPreferredTarget, tracker);
					Remember(preferredSummary, usedPreferredTarget: true);
					return preferredSummary;
				}
			}

			var targets = record.CompiledTargets;
			if (targets.Count > 0)
			{
				var target = SelectBestTarget(targets);
				var goalNode = BuildGoalContext(target);
				var targetNode = new ResolvedNodeContext(
					_guide.GetNodeKey(target.TargetNodeId),
					_guide.GetNode(target.TargetNodeId));
				var explanation = NavigationExplanationBuilder.Build(
					target.Semantic,
					goalNode,
					targetNode);
				string? requiredForContext = null;
				if (target.RequiredForQuestIndex >= 0)
				{
					requiredForContext =
						$"Needed for: {_guide.GetDisplayName(_guide.QuestNodeId(target.RequiredForQuestIndex))}";
				}
				var summary = new TrackerSummary(
					explanation.PrimaryText,
					target.Semantic.RationaleText,
					requiredForContext);
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
					value1: _lastSummaryText != null ? 1 : 0);
		}
	}

	private static ResolvedQuestTarget? FindCurrentPreferredTarget(
		IReadOnlyList<ResolvedQuestTarget> targets,
		ResolvedQuestTarget preferredTarget)
	{
		for (int i = 0; i < targets.Count; i++)
		{
			var candidate = targets[i];
			if (!string.Equals(candidate.TargetInstanceKey, preferredTarget.TargetInstanceKey, StringComparison.Ordinal))
				continue;
			if (!string.Equals(candidate.GoalNode.NodeKey, preferredTarget.GoalNode.NodeKey, StringComparison.Ordinal))
				continue;
			if (candidate.Semantic.ActionKind != preferredTarget.Semantic.ActionKind)
				continue;

			return candidate;
		}

		return null;
	}

	private static ResolvedQuestTarget RefreshPreferredTarget(
		ResolvedQuestTarget currentTarget,
		ResolvedQuestTarget preferredTarget)
	{
		if (!NavigationExplanationBuilder.IsZoneReentry(preferredTarget.Explanation))
			return currentTarget;
		if (NavigationExplanationBuilder.IsZoneReentry(currentTarget.Explanation))
			return currentTarget;

		return new ResolvedQuestTarget(
			currentTarget.TargetNodeKey,
			currentTarget.Scene,
			currentTarget.SourceKey,
			currentTarget.GoalNode,
			currentTarget.TargetNode,
			currentTarget.Semantic,
			preferredTarget.Explanation,
			currentTarget.X,
			currentTarget.Y,
			currentTarget.Z,
			currentTarget.IsActionable,
			currentTarget.RequiredForQuestKey,
			currentTarget.IsBlockedPath,
			currentTarget.IsGuaranteedLoot,
			currentTarget.AvailabilityPriority);
	}

	private TrackerSummary BuildPreferredTargetSummary(
		ResolvedQuestTarget target,
		QuestStateTracker tracker)
	{
		string? prerequisiteQuestName = null;
		if (!string.IsNullOrEmpty(target.RequiredForQuestKey)
			&& _guide.TryGetNodeId(target.RequiredForQuestKey, out int requiredQuestNodeId))
		{
			prerequisiteQuestName = _guide.GetDisplayName(requiredQuestNodeId);
		}

		var summary = NavigationExplanationBuilder.BuildTrackerSummary(
			target.GoalNode,
			target.Semantic,
			tracker,
			additionalCount: 0,
			prerequisiteQuestName);
		if (!NavigationExplanationBuilder.IsZoneReentry(target.Explanation))
			return summary;

		return new TrackerSummary(
			target.Explanation.PrimaryText,
			summary.SecondaryText ?? target.Explanation.SecondaryText,
			summary.RequiredForContext);
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
			lastSummaryText: _lastSummaryText);
	}

	private void Remember(TrackerSummary? summary, bool usedPreferredTarget)
	{
		_lastResolveUsedPreferredTarget = usedPreferredTarget;
		_lastSummaryText = summary?.PrimaryText;
	}
}
