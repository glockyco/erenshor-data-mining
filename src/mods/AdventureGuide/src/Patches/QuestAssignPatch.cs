using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

[HarmonyPatch(typeof(GameData), nameof(GameData.AssignQuest))]
internal static class QuestAssignPatch
{
    internal static QuestStateTracker? Tracker;

    [HarmonyPostfix]
    private static void Postfix(string _questName)
    {
        Tracker?.OnQuestAssigned(_questName);
    }
}
