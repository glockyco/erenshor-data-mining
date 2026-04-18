using AdventureGuide.Diagnostics;
using AdventureGuide.State;

namespace AdventureGuide.Plan;

/// <summary>
/// Decides whether maintained views (navigation, tracker, markers, detail)
/// must refresh and, if so, whether to rebuild fully or refresh a
/// subset of affected quest keys. Every maintained-view consumer reads the
/// same <see cref="MaintainedViewPlan"/>; no surface carries its own policy.
/// </summary>
internal static class MaintainedViewPlanner
{
	public static MaintainedViewPlan Plan(
		IEnumerable<string> activeKeys,
		GuideChangeSet changeSet,
		bool liveWorldChanged,
		bool targetSourceVersionChanged,
		bool navSetVersionChanged
	)
	{
		var activeSet = new HashSet<string>(StringComparer.Ordinal);
		foreach (var key in activeKeys)
			if (!string.IsNullOrWhiteSpace(key))
				activeSet.Add(key);

		if (activeSet.Count == 0)
			return MaintainedViewPlan.None;

		if (navSetVersionChanged)
			return Full(activeSet, DiagnosticTrigger.NavSetChanged);
		if (changeSet.SceneChanged)
			return Full(activeSet, DiagnosticTrigger.SceneChanged);
		if (targetSourceVersionChanged)
			return Full(activeSet, DiagnosticTrigger.TargetSourceVersionChanged);

		if (liveWorldChanged && changeSet.AffectedQuestKeys.Count == 0)
			return Full(activeSet, DiagnosticTrigger.LiveWorldChanged);

		if (!changeSet.HasMeaningfulChanges && !liveWorldChanged)
			return MaintainedViewPlan.None;

		if (changeSet.AffectedQuestKeys.Count == 0)
			return MaintainedViewPlan.None;

		var affected = new List<string>();
		foreach (var key in changeSet.AffectedQuestKeys)
		{
			if (activeSet.Contains(key))
				affected.Add(key);
		}

		if (affected.Count == 0)
			return MaintainedViewPlan.None;

		if (affected.Count == activeSet.Count)
			return Full(activeSet, DetermineReason(changeSet, liveWorldChanged));

		return new MaintainedViewPlan(
			MaintainedViewRefreshKind.Partial,
			affected.ToArray(),
			DetermineReason(changeSet, liveWorldChanged)
		);
	}

	private static MaintainedViewPlan Full(HashSet<string> activeSet, DiagnosticTrigger reason)
	{
		var keys = new string[activeSet.Count];
		int i = 0;
		foreach (var key in activeSet)
			keys[i++] = key;
		return new MaintainedViewPlan(MaintainedViewRefreshKind.Full, keys, reason);
	}

	private static DiagnosticTrigger DetermineReason(GuideChangeSet changeSet, bool liveWorldChanged)
	{
		if (changeSet.InventoryChanged)
			return DiagnosticTrigger.InventoryChanged;
		if (changeSet.QuestLogChanged)
			return DiagnosticTrigger.QuestLogChanged;
		if (liveWorldChanged)
			return DiagnosticTrigger.LiveWorldChanged;
		return DiagnosticTrigger.Unknown;
	}
}
