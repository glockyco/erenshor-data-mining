using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Notifies live-state and guide systems when an item bag changes so marker and
/// navigation invalidation can stay source-local.
/// </summary>
[HarmonyPatch(typeof(ItemBag), nameof(ItemBag.PickUp))]
internal static class ItemBagPatch
{
	internal static LiveStateTracker? LiveState;

	[HarmonyPostfix]
	private static void Postfix(ItemBag __instance)
	{
		LiveState?.OnItemBagChanged(__instance);
	}
}
