using AdventureGuide.Data;
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

    bool ReadAccountState(string key);

    string? ReadCharacterZoneState(string key);

    Vector3? ReadCharacterPositionState(string key);

    int PlayerLevel { get; }
}

internal sealed class LiveQuestGameState : IQuestGameState
{
    public static readonly LiveQuestGameState Instance = new();

    private LiveQuestGameState() { }

    public int PlayerLevel => GameData.PlayerStats != null ? GameData.PlayerStats.Level : 0;

    public bool ReadAccountState(string key) =>
        key switch
        {
            EncounterStateKeys.ReliquaryClaimed => GameData.AccountClaimedReliquary,
            _ => throw new ArgumentException($"Unknown account state {key}", nameof(key)),
        };

    public string? ReadCharacterZoneState(string key) =>
        key switch
        {
            EncounterStateKeys.ReturnZone => GameData.ReliqDest,
            _ => throw new ArgumentException($"Unknown character zone state {key}", nameof(key)),
        };

    public Vector3? ReadCharacterPositionState(string key) =>
        key switch
        {
            EncounterStateKeys.ReturnLanding => GameData.ReliqLanding,
            _ => throw new ArgumentException(
                $"Unknown character position state {key}",
                nameof(key)
            ),
        };

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
            if (slot?.MyItem == null || slot.MyItem == GameData.PlayerInv.Empty)
                continue;
            var key = "item:" + slot.MyItem.name.Trim().ToLowerInvariant();
            InventoryCountPolicy.Add(
                destination,
                key,
                slot.MyItem.RequiredSlot == Item.SlotType.General,
                slot.Quantity
            );
        }
    }
}
