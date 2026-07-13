using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Observes every runtime character after its components are initialized.
/// Scripted workflow targets are not guaranteed to originate from SpawnPoint,
/// so the regular spawn patch cannot cover this lifecycle boundary.
/// </summary>
[HarmonyPatch(typeof(Character), "Start")]
internal static class ScriptedEntityStartPatch
{
    internal static QuestStateTracker? Tracker;

    [HarmonyPostfix]
    private static void Postfix(Character __instance) => Tracker?.OnCharacterStarted(__instance);
}

/// <summary>
/// LootWindow calls NPC.ExpediteRot only after every item has been removed
/// from an NPC corpse. That explicit loot boundary is stronger evidence than
/// proximity or object disappearance for workflow reward completion.
/// </summary>
[HarmonyPatch(typeof(NPC), nameof(NPC.ExpediteRot), new System.Type[0])]
internal static class ScriptedRewardConsumedPatch
{
    internal static QuestStateTracker? Tracker;

    [HarmonyPostfix]
    private static void Postfix(NPC __instance)
    {
        var character = __instance.GetChar();
        if (character != null)
            Tracker?.OnRewardContainerConsumed(character);
    }
}
