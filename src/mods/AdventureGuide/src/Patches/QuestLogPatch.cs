using AdventureGuide.Config;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Suppresses the native journal-key toggle when ReplaceQuestLog is enabled.
/// Prefix and original see the same frame's key-down state. Other frames must
/// run the original Update so its Escape-to-close handler remains available.
/// </summary>
[HarmonyPatch(typeof(QuestLog), "Update")]
internal static class QuestLogPatch
{
    internal static IConfigValue<bool>? ReplaceQuestLog;

    [HarmonyPrefix]
    private static bool Prefix() =>
        QuestLogSuppressionPolicy.ShouldRunOriginal(
            ReplaceQuestLog is { Value: true },
            UnityEngine.Input.GetKeyDown(InputManager.Journal)
        );
}
