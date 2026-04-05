using AdventureGuide.Markers;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Registers spawned NPCs in live-world state and propagates precise source changes
/// the guide invalidation pipeline.
/// </summary>
[HarmonyPatch(typeof(SpawnPoint), "SpawnNPC")]
internal static class SpawnPatch
{
    internal static LiveStateTracker? LiveState;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(SpawnPoint __instance)
    {
        var changeSet = LiveState?.OnNPCSpawn(__instance) ?? GuideChangeSet.None;
        Markers?.ApplyGuideChangeSet(changeSet);
    }
}
