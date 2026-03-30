using AdventureGuide.Markers;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Patches Inventory.UpdatePlayerInventory and propagates structured inventory
/// deltas into the guide marker pipeline.
/// </summary>
[HarmonyPatch(typeof(Inventory), nameof(Inventory.UpdatePlayerInventory))]
internal static class InventoryPatch
{
    internal static QuestStateTracker? Tracker;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix()
    {
        var changeSet = Tracker?.OnInventoryChanged() ?? GuideChangeSet.None;
        Markers?.ApplyGuideChangeSet(changeSet);
    }
}
