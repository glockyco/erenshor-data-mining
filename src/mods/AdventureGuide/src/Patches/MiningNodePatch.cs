using AdventureGuide.Markers;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Notifies live-state and marker systems when a mining node is mined so
/// navigation and markers can reroute immediately.
/// </summary>
[HarmonyPatch(typeof(MiningNode), nameof(MiningNode.Mine))]
internal static class MiningNodePatch
{
    internal static LiveStateTracker? LiveState;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(MiningNode __instance)
    {
        LiveState?.OnMiningChanged(__instance);
        Markers?.MarkDirty();
    }
}
