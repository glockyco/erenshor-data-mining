using UnityEngine;

namespace AdventureGuide.State;

/// <summary>
/// Narrow read boundary between quest logic and the game's static state.
/// Production reads GameData; tests provide deterministic snapshots without
/// loading Unity engine singletons.
/// </summary>
internal interface IQuestGameState
{
    void CopyActiveQuestsTo(HashSet<string> destination);

    void CopyCompletedQuestsTo(HashSet<string> destination);

    void CopyInventoryCountsTo(Dictionary<string, int> destination);

    Vector3? PlayerPosition { get; }
}

internal sealed class LiveQuestGameState : IQuestGameState
{
    public static readonly LiveQuestGameState Instance = new();

    private LiveQuestGameState() { }

    public Vector3? PlayerPosition =>
        GameData.PlayerControl != null ? GameData.PlayerControl.transform.position : null;

    public void CopyActiveQuestsTo(HashSet<string> destination)
    {
        if (GameData.HasQuest == null)
            return;
        foreach (var quest in GameData.HasQuest)
            destination.Add(quest);
    }

    public void CopyCompletedQuestsTo(HashSet<string> destination)
    {
        if (GameData.CompletedQuests == null)
            return;
        foreach (var quest in GameData.CompletedQuests)
            destination.Add(quest);
    }

    public void CopyInventoryCountsTo(Dictionary<string, int> destination)
    {
        if (GameData.PlayerInv?.StoredSlots == null)
            return;

        foreach (var slot in GameData.PlayerInv.StoredSlots)
        {
            if (slot?.MyItem == null)
                continue;
            var key = "item:" + slot.MyItem.name.Trim().ToLowerInvariant();
            destination[key] = destination.TryGetValue(key, out int count) ? count + 1 : 1;
        }
    }
}
