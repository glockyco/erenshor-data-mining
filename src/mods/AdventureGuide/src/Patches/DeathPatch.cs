using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Unregisters dying NPCs from the EntityRegistry and notifies
/// LiveStateTracker to start tracking respawn timers.
/// </summary>
[HarmonyPatch(typeof(Character), "DoDeath")]
internal static class DeathPatch
{
    internal static EntityRegistry? Registry;
    internal static LiveStateTracker? LiveState;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(Character __instance)
    {
        var npc = __instance.GetComponent<NPC>();
        if (npc == null) return;
        Registry?.Unregister(npc);
        LiveState?.OnNPCDeath(npc);
        Markers?.MarkDirty();
    }
}
