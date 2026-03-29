using AdventureGuide.Markers;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Patches Inventory.UpdatePlayerInventory to notify AdventureGuide only when
/// the underlying inventory contents actually changed. The game also calls this
/// method for inventory UI refreshes such as open/close, so the tracker must
/// fast-path no-op refreshes instead of treating them as world-state changes.
/// </summary>
[HarmonyPatch(typeof(Inventory), nameof(Inventory.UpdatePlayerInventory))]
internal static class InventoryPatch
{
    internal static QuestStateTracker? Tracker;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix()
    {
        if (Tracker?.OnInventoryChanged() == true)
            Markers?.MarkDirty();
    }
}
