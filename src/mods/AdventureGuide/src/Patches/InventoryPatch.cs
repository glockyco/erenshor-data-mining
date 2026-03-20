using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Patches both overloads of AddItemToInv and RemoveItemFromInv to set the
/// dirty flag on QuestStateTracker. We don't capture parameters — we only
/// need to know the inventory changed.
/// </summary>
[HarmonyPatch]
internal static class InventoryPatch
{
    internal static QuestStateTracker? Tracker;

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItemToInv), typeof(Item))]
    [HarmonyPostfix]
    private static void AddItemPostfix() => Tracker?.OnInventoryChanged();

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItemToInv), typeof(Item), typeof(int))]
    [HarmonyPostfix]
    private static void AddItemQualPostfix() => Tracker?.OnInventoryChanged();

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.RemoveItemFromInv), typeof(ItemIcon))]
    [HarmonyPostfix]
    private static void RemoveBySlotPostfix() => Tracker?.OnInventoryChanged();

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.RemoveItemFromInv), typeof(Item))]
    [HarmonyPostfix]
    private static void RemoveByItemPostfix() => Tracker?.OnInventoryChanged();
}
