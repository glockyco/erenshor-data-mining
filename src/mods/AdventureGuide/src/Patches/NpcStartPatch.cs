using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Records prefab or placement identity before NPC.Start renames the GameObject.
/// Scene placements join the navigation registry and world markers, including
/// objects an event enables later. Script-instantiated clones join the registry
/// by prefab key. SpawnPoint clones were already registered by SpawnPatch.
/// </summary>
[HarmonyPatch(typeof(NPC), "Start")]
internal static class NpcStartPatch
{
    internal static WorldMarkerSystem? Markers;
    internal static EntityRegistry? Entities;

    [HarmonyPrefix]
    private static void Prefix(NPC __instance)
    {
        NpcOrigins.Record(__instance);
        if (NpcOrigins.PlacedName(__instance) == null)
        {
            if (Entities != null && !Entities.IsSpawnPointNpc(__instance))
                Entities.Register(__instance);
            return;
        }
        Entities?.RegisterPlaced(__instance);
        Markers?.OnNpcStarted(__instance);
    }
}
