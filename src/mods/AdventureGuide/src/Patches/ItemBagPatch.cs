using AdventureGuide.Markers;
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
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(ItemBag __instance)
    {
        var changeSet = LiveState?.OnItemBagChanged(__instance) ?? GuideChangeSet.None;
        Markers?.ApplyGuideChangeSet(changeSet);
    }
}
