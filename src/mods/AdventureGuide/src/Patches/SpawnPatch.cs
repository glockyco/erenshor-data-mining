using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Registers spawned NPCs and propagates precise live-world source changes into
/// the guide invalidation pipeline.
/// </summary>
[HarmonyPatch(typeof(SpawnPoint), "SpawnNPC")]
internal static class SpawnPatch
{
    internal static EntityRegistry? Registry;
    internal static LiveStateTracker? LiveState;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(SpawnPoint __instance)
    {
        if (__instance.SpawnedNPC != null)
            Registry?.Register(__instance.SpawnedNPC, __instance);

        var changeSet = LiveState?.OnNPCSpawn(__instance) ?? GuideChangeSet.None;
        Markers?.ApplyGuideChangeSet(changeSet);
    }
}
