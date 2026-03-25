using BepInEx.Configuration;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Suppresses the native quest journal when ReplaceQuestLog is enabled.
/// The game's QuestLog.Update checks InputManager.Journal each frame and
/// toggles the journal window. This prefix skips that entire method so
/// Plugin.Update can open the Adventure Guide on the same key instead.
/// </summary>
[HarmonyPatch(typeof(QuestLog), "Update")]
internal static class QuestLogPatch
{
    internal static ConfigEntry<bool>? ReplaceQuestLog;

    [HarmonyPrefix]
    private static bool Prefix() => ReplaceQuestLog is not { Value: true };
}
