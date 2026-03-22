using AdventureGuide.Navigation;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Patches both overloads of AddItemToInv and RemoveItemFromInv to notify
/// QuestStateTracker (invalidates inventory cache) and NavigationController
/// (may auto-advance collect steps).
/// </summary>
[HarmonyPatch]
internal static class InventoryPatch
{
    internal static QuestStateTracker? Tracker;
    internal static NavigationController? Nav;

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItemToInv), typeof(Item))]
    [HarmonyPostfix]
    private static void AddItemPostfix() => OnChanged();

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.AddItemToInv), typeof(Item), typeof(int))]
    [HarmonyPostfix]
    private static void AddItemQualPostfix() => OnChanged();

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.RemoveItemFromInv), typeof(ItemIcon))]
    [HarmonyPostfix]
    private static void RemoveBySlotPostfix() => OnChanged();

    [HarmonyPatch(typeof(Inventory), nameof(Inventory.RemoveItemFromInv), typeof(Item))]
    [HarmonyPostfix]
    private static void RemoveByItemPostfix() => OnChanged();

    private static void OnChanged()
    {
        Tracker?.OnInventoryChanged();
        Nav?.OnGameStateChanged(Tracker?.CurrentZone ?? "");
    }
}
