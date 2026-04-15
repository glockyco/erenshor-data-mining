using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;


public static class TrackerSummaryBuilder
{
    public static TrackerSummary Build(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        FrontierEntry entry)
    {
        var summary = entry.Phase switch
        {
            QuestPhase.ReadyToAccept => BuildReadyToAccept(guide, entry.QuestIndex),
            QuestPhase.Accepted => BuildAccepted(guide, phases, entry.QuestIndex),
            QuestPhase.NotReady => new TrackerSummary($"Complete: {guide.GetDisplayName(guide.PrereqQuestIds(entry.QuestIndex)[0])}"),
            _ => new TrackerSummary(guide.GetDisplayName(guide.QuestNodeId(entry.QuestIndex))),
        };

        if (entry.RequiredForQuestIndex >= 0)
        {
            string parentName = guide.GetDisplayName(guide.QuestNodeId(entry.RequiredForQuestIndex));
            return new TrackerSummary(summary.PrimaryText, summary.SecondaryText, $"Needed for: {parentName}");
        }

        return summary;
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
            			if (itemIndex < 0)
            			{
            				return new TrackerSummary(
            					$"Collect [Unknown] (0/{requirement.Quantity})");
            			}
            			int count = phases.GetItemCount(itemIndex);
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
