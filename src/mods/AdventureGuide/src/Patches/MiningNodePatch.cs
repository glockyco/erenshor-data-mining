using AdventureGuide.Markers;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Notifies live-state and guide systems when a mining node changes so marker
/// and navigation invalidation can stay source-local.
/// </summary>
[HarmonyPatch(typeof(MiningNode), nameof(MiningNode.Mine))]
internal static class MiningNodePatch
{
    internal static LiveStateTracker? LiveState;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(MiningNode __instance)
    {
        var changeSet = LiveState?.OnMiningChanged(__instance) ?? GuideChangeSet.None;
        Markers?.ApplyGuideChangeSet(changeSet);
    }
}
