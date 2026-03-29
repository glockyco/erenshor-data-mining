using AdventureGuide.Markers;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Notifies live-state and marker systems when an item bag is picked up so
/// navigation and markers stop pointing at a destroyed bag.
/// </summary>
[HarmonyPatch(typeof(ItemBag), nameof(ItemBag.PickUp))]
internal static class ItemBagPatch
{
    internal static LiveStateTracker? LiveState;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(ItemBag __instance)
    {
        LiveState?.OnItemBagChanged(__instance);
        Markers?.MarkDirty();
    }
}
