using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Registers newly spawned NPCs in the EntityRegistry, clears any respawn
/// timer tracked by SpawnTimerTracker, and records the NPC for world markers.
/// SpawnPoint.SpawnNPC sets SpawnedNPC and adds to NPCTable.LiveNPCs
/// before this postfix runs, so NPCName is available.
/// </summary>
[HarmonyPatch(typeof(SpawnPoint), "SpawnNPC")]
internal static class SpawnPatch
{
    internal static EntityRegistry? Registry;
    internal static SpawnTimerTracker? Timers;
    internal static WorldMarkerSystem? Markers;
    internal static LootScanner? Loot;

    [HarmonyPostfix]
    private static void Postfix(SpawnPoint __instance)
    {
        if (__instance.SpawnedNPC != null)
            Registry?.Register(__instance.SpawnedNPC, __instance);

        Timers?.OnNPCSpawn(__instance);
        Markers?.OnNPCSpawned(__instance);
        Loot?.MarkDirty();
    }
}
