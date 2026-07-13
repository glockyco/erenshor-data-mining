using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Tests;

internal sealed class TestQuestGameState : IQuestGameState
{
    public HashSet<string> ActiveQuests { get; } = new(StringComparer.OrdinalIgnoreCase);
    public HashSet<string> CompletedQuests { get; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<string, int> Inventory { get; } = new(StringComparer.OrdinalIgnoreCase);
    public Vector3? PlayerPosition { get; set; }

    public void CopyActiveQuestsTo(HashSet<string> destination) =>
        destination.UnionWith(ActiveQuests);

    public void CopyCompletedQuestsTo(HashSet<string> destination) =>
        destination.UnionWith(CompletedQuests);

    public void CopyInventoryCountsTo(Dictionary<string, int> destination)
    {
        foreach (var (key, count) in Inventory)
            destination.Add(key, count);
    }
}
