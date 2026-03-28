using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Registers newly spawned NPCs in the EntityRegistry and notifies
/// LiveStateTracker to clear respawn timers.
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
        LiveState?.OnNPCSpawn(__instance);
        Markers?.MarkDirty();
    }
}
