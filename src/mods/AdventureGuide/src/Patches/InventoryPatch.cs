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

	[HarmonyPostfix]
	private static void Postfix()
	{
		Tracker?.OnInventoryChanged();
	}
}
