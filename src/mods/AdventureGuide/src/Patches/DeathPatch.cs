using AdventureGuide.Markers;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Unregisters dying NPCs and propagates precise live-world source changes into
/// the guide invalidation pipeline.
/// </summary>
[HarmonyPatch(typeof(Character), "DoDeath")]
internal static class DeathPatch
{
    internal static LiveStateTracker? LiveState;
    internal static MarkerComputer? Markers;

    [HarmonyPostfix]
    private static void Postfix(Character __instance)
    {
        var npc = __instance.GetComponent<NPC>();
        if (npc == null)
            return;

        var changeSet = LiveState?.OnNPCDeath(npc) ?? GuideChangeSet.None;
        Markers?.ApplyGuideChangeSet(changeSet);
    }
}
