using AdventureGuide.CompiledGuide;
using AdventureGuide.Frontier;

namespace AdventureGuide.Resolution;

public sealed class QuestDetailState
{
	private readonly QuestPhase[] _phases;
	private readonly int[] _itemCounts;

	public QuestDetailState(QuestPhase[] phases, int[] itemCounts)
	{
		_phases = (QuestPhase[])phases.Clone();
		_itemCounts = (int[])itemCounts.Clone();
	}

	public static QuestDetailState Capture(
		CompiledGuide.CompiledGuide guide,
		QuestPhaseTracker phases)
	{
		var phaseSnapshot = new QuestPhase[guide.QuestCount];
		for (int questIndex = 0; questIndex < phaseSnapshot.Length; questIndex++)
			phaseSnapshot[questIndex] = phases.GetPhase(questIndex);

		var itemCounts = new int[guide.ItemCount];
		for (int itemIndex = 0; itemIndex < itemCounts.Length; itemIndex++)
			itemCounts[itemIndex] = phases.GetItemCount(itemIndex);

		return new QuestDetailState(phaseSnapshot, itemCounts);
	}

	public bool HasSameSnapshot(QuestDetailState other)
	{
		return _phases.SequenceEqual(other._phases)
			&& _itemCounts.SequenceEqual(other._itemCounts);
	}

	public override bool Equals(object? obj) =>
		obj is QuestDetailState other && HasSameSnapshot(other);

	public override int GetHashCode()
	{
		var hash = new HashCode();
		for (int i = 0; i < _phases.Length; i++)
			hash.Add(_phases[i]);
		for (int i = 0; i < _itemCounts.Length; i++)
			hash.Add(_itemCounts[i]);
		return hash.ToHashCode();
	}

	public QuestPhase GetPhase(int questIndex) => _phases[questIndex];

	public bool IsQuestCompleted(int questIndex) => _phases[questIndex] == QuestPhase.Completed;

	public int GetItemCount(int itemIndex) => _itemCounts[itemIndex];

	public bool IsQuestNodeCompleted(CompiledGuide.CompiledGuide guide, int nodeId)
	{
		int questIndex = guide.FindQuestIndex(nodeId);
		return questIndex >= 0 && IsQuestCompleted(questIndex);
	}

	public IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> GetBlockingRequirementGroups(
		CompiledGuide.CompiledGuide guide,
		int targetNodeId)
	{
		if (!guide.TryGetUnlockPredicate(targetNodeId, out var predicate))
			return Array.Empty<IReadOnlyList<UnlockConditionEntry>>();

		var conditions = predicate.Conditions;
		if (predicate.Semantics == 0)
		{
			var unmet = conditions
				.Where(condition => !IsUnlockConditionSatisfied(guide, condition))
				.ToArray();
			return unmet.Length == 0
				? Array.Empty<IReadOnlyList<UnlockConditionEntry>>()
				: new IReadOnlyList<UnlockConditionEntry>[] { unmet };
		}

		var unconditional = conditions
			.Where(condition => condition.Group == 0 && !IsUnlockConditionSatisfied(guide, condition))
			.ToArray();
		var groups = new List<IReadOnlyList<UnlockConditionEntry>>();
		for (int group = 1; group <= predicate.GroupCount; group++)
		{
			bool hadConditions = false;
			var grouped = new List<UnlockConditionEntry>();
			foreach (var condition in conditions)
			{
				if (condition.Group != group)
					continue;

				hadConditions = true;
				if (!IsUnlockConditionSatisfied(guide, condition))
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

	public bool IsUnlockConditionSatisfied(
		CompiledGuide.CompiledGuide guide,
		UnlockConditionEntry condition)
	{
		if (condition.CheckType == 0)
		{
			int questIndex = guide.FindQuestIndex(condition.SourceId);
			return questIndex >= 0 && IsQuestCompleted(questIndex);
		}

		int itemIndex = guide.FindItemIndex(condition.SourceId);
		return itemIndex >= 0 && GetItemCount(itemIndex) > 0;
	}
}
