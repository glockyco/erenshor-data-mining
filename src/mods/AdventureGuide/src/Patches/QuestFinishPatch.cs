using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

[HarmonyPatch(typeof(GameData), nameof(GameData.FinishQuest))]
internal static class QuestFinishPatch
{
    internal static QuestStateTracker? Tracker;

    [HarmonyPostfix]
    private static void Postfix(string _questName)
    {
        Tracker?.OnQuestCompleted(_questName);
    }
}
