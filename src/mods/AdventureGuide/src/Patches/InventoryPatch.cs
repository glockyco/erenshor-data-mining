using AdventureGuide.Markers;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Patches Inventory.UpdatePlayerInventory to notify QuestStateTracker and
/// trigger marker recomputation when inventory contents change. This is the
/// single centralized method called by all inventory mutations: AddItemToInv,
/// ForceItemToInv, RemoveItemFromInv, RemoveStackFromInv, and equipment
/// changes.
/// </summary>
[HarmonyPatch(typeof(Inventory), nameof(Inventory.UpdatePlayerInventory))]
internal static class InventoryPatch
{
    internal static QuestStateTracker? Tracker;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix()
    {
        Tracker?.OnInventoryChanged();
        Markers?.MarkDirty();
    }
}
