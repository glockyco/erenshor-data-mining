using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Records an NPC's object name (its prefab, or its scene object name and
/// position) before NPC.Start renames the GameObject to NPCName. NPCs placed
/// in the scene then join the navigation registry and world markers; this
/// also covers scene objects an event switches on after the scene loaded.
/// Spawned clones reach both through the SpawnNPC postfix instead. Character
/// Start, which workflows observe, may run before or after NPC.Start on the
/// same object.
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
            return;
        Entities?.RegisterPlaced(__instance);
        Markers?.OnNpcStarted(__instance);
    }
}
