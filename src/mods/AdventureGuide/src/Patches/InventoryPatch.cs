using AdventureGuide.Navigation;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Observes inventory UI refreshes, including removals and equipment changes.
/// Item grants refresh the UI only while the bag is open; InventoryGrantPatch
/// observes those mutations directly so closed-bag grants are not missed.
/// </summary>
[HarmonyPatch(typeof(Inventory), nameof(Inventory.UpdatePlayerInventory))]
internal static class InventoryPatch
{
    internal static QuestStateTracker? Tracker;
    internal static NavigationController? Nav;
    internal static LootScanner? Loot;

    [HarmonyPostfix]
    private static void Postfix() => NotifyChanged();

    internal static void NotifyChanged()
    {
        Tracker?.OnInventoryChanged();
        Nav?.OnGameStateChanged(Tracker?.CurrentZone ?? "");
        Loot?.MarkDirty();
    }
}
