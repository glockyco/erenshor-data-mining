using AdventureGuide.Frontier;

namespace AdventureGuide.Tests.Helpers;

internal static class QuestPhaseTrackerTestExtensions
{
    public static void Initialize(
        this QuestPhaseTracker tracker,
        IReadOnlyCollection<string> completedQuestDbNames,
        IReadOnlyCollection<string> activeQuestDbNames,
        IReadOnlyDictionary<string, int> inventory,
        IReadOnlyCollection<string> keyringItems
    )
    {
        tracker.State.LoadState(
            currentZone: string.Empty,
            activeQuests: activeQuestDbNames,
            completedQuests: completedQuestDbNames,
            inventoryCounts: inventory,
            keyringItemKeys: keyringItems
        );
    }

    public static void OnQuestAssigned(this QuestPhaseTracker tracker, int questIndex)
    {
        string dbName = tracker.Guide.GetDbName(tracker.Guide.QuestNodeId(questIndex))
            ?? throw new InvalidOperationException($"Quest index {questIndex} has no db name.");
        tracker.State.OnQuestAssigned(dbName);
    }

    public static void OnQuestCompleted(this QuestPhaseTracker tracker, int questIndex)
    {
        string dbName = tracker.Guide.GetDbName(tracker.Guide.QuestNodeId(questIndex))
            ?? throw new InvalidOperationException($"Quest index {questIndex} has no db name.");
        tracker.State.OnQuestCompleted(dbName);
    }

    public static void OnInventoryChanged(this QuestPhaseTracker tracker, int itemIndex, int newCount)
    {
        string itemKey = tracker.Guide.GetNodeKey(tracker.Guide.ItemNodeId(itemIndex));
        var inventory = new Dictionary<string, int>(tracker.State.InventoryCounts, StringComparer.Ordinal);
        if (newCount > 0)
            inventory[itemKey] = newCount;
        else
            inventory.Remove(itemKey);

        tracker.State.LoadState(
            tracker.State.CurrentZone,
            tracker.State.ActiveQuests.ToArray(),
            tracker.State.CompletedQuests.ToArray(),
            inventory,
            tracker.State.KeyringItems.ToArray()
        );
    }
}
