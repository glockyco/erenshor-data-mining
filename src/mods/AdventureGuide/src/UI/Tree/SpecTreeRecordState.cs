using AdventureGuide.Resolution;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;
using UnlockConditionEntry = AdventureGuide.CompiledGuide.UnlockConditionEntry;

namespace AdventureGuide.UI.Tree;

internal static class SpecTreeRecordState
{
	public static IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> GetBlockingRequirementGroups(
        CompiledGuideModel guide,
		QuestResolutionRecord record,
		int targetNodeId
	)
	{
		if (!guide.TryGetUnlockPredicate(targetNodeId, out var predicate))
			return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();

		if (predicate.Semantics == 0)
		{
			var unmet = predicate.Conditions.Where(condition => !IsUnlockConditionSatisfied(guide, record, condition)).ToArray();
			return unmet.Length == 0
				? Array.Empty<IReadOnlyList<UnlockConditionEntry>>()
				: new IReadOnlyList<UnlockConditionEntry>[] { unmet };
		}

		var unconditional = predicate
			.Conditions.Where(condition => condition.Group == 0 && !IsUnlockConditionSatisfied(guide, record, condition))
			.ToArray();
		var groups = new List<IReadOnlyList<UnlockConditionEntry>>();
		for (int group = 1; group <= predicate.GroupCount; group++)
		{
			bool hadConditions = false;
			var grouped = new List<UnlockConditionEntry>();
			foreach (var condition in predicate.Conditions)
			{
				if (condition.Group != group)
					continue;

				hadConditions = true;
				if (!IsUnlockConditionSatisfied(guide, record, condition))
					grouped.Add(condition);
			}

			if (!hadConditions)
				continue;
			if (grouped.Count == 0 && unconditional.Length == 0)
				return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();
			groups.Add(unconditional.Concat(grouped).ToArray());
		}

		if (groups.Count == 0 && unconditional.Length > 0)
			groups.Add(unconditional);
		return groups;
	}

	public static bool IsUnlockConditionSatisfied(
        CompiledGuideModel guide,
		QuestResolutionRecord record,
		UnlockConditionEntry condition
	)
	{
		if (condition.CheckType == 0)
		{
			int questIndex = guide.FindQuestIndex(condition.SourceId);
			return questIndex >= 0 && record.IsQuestCompleted(questIndex);
		}

		int itemIndex = guide.FindItemIndex(condition.SourceId);
		return itemIndex >= 0 && record.GetItemCount(itemIndex) > 0;
	}

	public static bool IsQuestNodeCompleted(
        CompiledGuideModel guide,
		QuestResolutionRecord record,
		int nodeId
	)
	{
		int questIndex = guide.FindQuestIndex(nodeId);
		return questIndex >= 0 && record.IsQuestCompleted(questIndex);
	}

	public static int? FindBlockingZoneLineNodeId(QuestResolutionRecord record, string? targetScene)
	{
		if (string.IsNullOrWhiteSpace(targetScene))
			return null;

		return record.TryGetBlockingZoneLineNodeId(targetScene, out int zoneLineNodeId)
			? zoneLineNodeId
			: null;
	}
}
