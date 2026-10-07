using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Records an instantiated NPC's prefab before NPC.Start renames its
/// GameObject to NPCName. Character.Start, which workflows observe, may run
/// before or after NPC.Start on the same object.
/// </summary>
[HarmonyPatch(typeof(NPC), "Start")]
internal static class NpcStartPatch
{
    [HarmonyPrefix]
    private static void Prefix(NPC __instance) => NpcOrigins.Record(__instance);
}
