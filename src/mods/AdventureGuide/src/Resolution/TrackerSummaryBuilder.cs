using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;


public static class TrackerSummaryBuilder
{
    public static TrackerSummary Build(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        FrontierEntry entry)
    {
        return entry.Phase switch
        {
            QuestPhase.ReadyToAccept => BuildReadyToAccept(guide, entry.QuestIndex),
            QuestPhase.Accepted => BuildAccepted(guide, phases, entry.QuestIndex),
            QuestPhase.NotReady => new TrackerSummary($"Complete: {guide.GetDisplayName(guide.PrereqQuestIds(entry.QuestIndex)[0])}"),
            _ => new TrackerSummary(guide.GetDisplayName(guide.QuestNodeId(entry.QuestIndex))),
        };
    }

    private static TrackerSummary BuildReadyToAccept(CompiledGuide.CompiledGuide guide, int questIndex)
    {
        ReadOnlySpan<int> giverIds = guide.GiverIds(questIndex);
        if (giverIds.Length == 0)
        {
            return new TrackerSummary($"Accept {guide.GetDisplayName(guide.QuestNodeId(questIndex))}");
        }

        return new TrackerSummary($"Talk to {guide.GetDisplayName(giverIds[0])}");
    }

    private static TrackerSummary BuildAccepted(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        int questIndex)
    {
        foreach (var requirement in guide.RequiredItems(questIndex))
        {
            int itemIndex = guide.FindItemIndex(requirement.ItemId);
            int count = itemIndex >= 0 ? phases.GetItemCount(itemIndex) : 0;
            if (count < requirement.Quantity)
            {
                return new TrackerSummary(
                    $"Collect {guide.GetDisplayName(requirement.ItemId)} ({count}/{requirement.Quantity})");
            }
        }

        foreach (var step in guide.Steps(questIndex))
        {
            return new TrackerSummary($"Complete {guide.GetDisplayName(step.TargetId)}");
        }

        ReadOnlySpan<int> completerIds = guide.CompleterIds(questIndex);
        if (completerIds.Length > 0)
        {
            return new TrackerSummary($"Turn in to {guide.GetDisplayName(completerIds[0])}");
        }

        return new TrackerSummary($"Complete {guide.GetDisplayName(guide.QuestNodeId(questIndex))}");
    }
}
