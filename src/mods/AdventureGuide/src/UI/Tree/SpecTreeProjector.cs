using AdventureGuide.CompiledGuide;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;

namespace AdventureGuide.UI.Tree;

public sealed class SpecTreeProjector
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly UnlockPredicateEvaluator _unlocks;

    public SpecTreeProjector(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks)
    {
        _guide = guide;
        _phases = phases;
        _unlocks = unlocks;
    }

    public IReadOnlyList<SpecTreeRef> GetRootChildren(int questIndex)
    {
        var results = new List<SpecTreeRef>();

        foreach (int prereqId in _guide.PrereqQuestIds(questIndex))
        {
            int prereqQuestIndex = FindQuestIndex(prereqId);
            bool done = prereqQuestIndex >= 0 && _phases.IsCompleted(prereqQuestIndex);
            results.Add(new SpecTreeRef(
                prereqId,
                SpecTreeKind.Prerequisite,
                questIndex,
                _guide.GetDisplayName(prereqId),
                done,
                false));
        }

        foreach (int giverId in _guide.GiverIds(questIndex))
        {
            results.Add(new SpecTreeRef(
                giverId,
                SpecTreeKind.Giver,
                questIndex,
                _guide.GetDisplayName(giverId),
                false,
                _unlocks.Evaluate(giverId) == UnlockResult.Blocked));
        }

        foreach (var requirement in _guide.RequiredItems(questIndex))
        {
            int itemIndex = FindItemIndex(requirement.ItemId);
            int have = itemIndex >= 0 ? _phases.GetItemCount(itemIndex) : 0;
            results.Add(new SpecTreeRef(
                requirement.ItemId,
                SpecTreeKind.Item,
                questIndex,
                _guide.GetDisplayName(requirement.ItemId),
                have >= requirement.Quantity,
                false));
        }

        foreach (var step in _guide.Steps(questIndex))
        {
            results.Add(new SpecTreeRef(
                step.TargetId,
                SpecTreeKind.Step,
                questIndex,
                _guide.GetDisplayName(step.TargetId),
                false,
                false));
        }

        foreach (int completerId in _guide.CompleterIds(questIndex))
        {
            results.Add(new SpecTreeRef(
                completerId,
                SpecTreeKind.Completer,
                questIndex,
                _guide.GetDisplayName(completerId),
                false,
                _unlocks.Evaluate(completerId) == UnlockResult.Blocked));
        }

        return results;
    }

    public IReadOnlyList<SpecTreeRef> GetChildren(SpecTreeRef parent)
    {
        if (parent.Kind != SpecTreeKind.Item)
        {
            return Array.Empty<SpecTreeRef>();
        }

        int itemIndex = FindItemIndex(parent.NodeId);
        if (itemIndex < 0)
        {
            return Array.Empty<SpecTreeRef>();
        }

        var results = new List<SpecTreeRef>();
        foreach (var source in _guide.GetItemSources(itemIndex))
        {
            results.Add(new SpecTreeRef(
                source.SourceId,
                SpecTreeKind.Source,
                parent.QuestIndex,
                _guide.GetDisplayName(source.SourceId),
                false,
                _unlocks.Evaluate(source.SourceId) == UnlockResult.Blocked));
        }

        return results;
    }

    private int FindQuestIndex(int nodeId)
    {
        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            if (_guide.QuestNodeId(questIndex) == nodeId)
            {
                return questIndex;
            }
        }

        return -1;
    }

    private int FindItemIndex(int nodeId)
    {
        for (int itemIndex = 0; itemIndex < _guide.ItemCount; itemIndex++)
        {
            if (_guide.ItemNodeId(itemIndex) == nodeId)
            {
                return itemIndex;
            }
        }

        return -1;
    }
}
