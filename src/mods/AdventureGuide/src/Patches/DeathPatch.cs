using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Unregisters dying NPCs from the EntityRegistry and notifies
/// SpawnTimerTracker to start tracking respawn timers.
/// Character.DoDeath is private but Harmony patches it by name.
/// Only NPC characters (those with an NPC component) are tracked.
/// </summary>
[HarmonyPatch(typeof(Character), "DoDeath")]
internal static class DeathPatch
{
    internal static EntityRegistry? Registry;
    internal static SpawnTimerTracker? Timers;
    internal static WorldMarkerSystem? Markers;

    [HarmonyPostfix]
    private static void Postfix(Character __instance)
    {
        var npc = __instance.GetComponent<NPC>();
        if (npc == null) return;

        Registry?.Unregister(npc);
        Timers?.OnNPCDeath(npc);
        Markers?.MarkSpawnDirty();
    }
}
