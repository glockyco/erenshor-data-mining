using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Records an NPC's object name (its prefab, or its scene object name) before
/// NPC.Start renames the GameObject to NPCName, and tells world markers about
/// NPCs that start after the scene loaded. Character.Start, which workflows
/// observe, may run before or after NPC.Start on the same object.
/// </summary>
[HarmonyPatch(typeof(NPC), "Start")]
internal static class NpcStartPatch
{
    internal static WorldMarkerSystem? Markers;

    [HarmonyPrefix]
    private static void Prefix(NPC __instance)
    {
        NpcOrigins.Record(__instance);
        Markers?.OnNpcStarted(__instance);
    }
}
