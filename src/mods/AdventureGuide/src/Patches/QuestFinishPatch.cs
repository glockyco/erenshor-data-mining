using AdventureGuide.Markers;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

[HarmonyPatch(typeof(GameData), nameof(GameData.FinishQuest))]
internal static class QuestFinishPatch
{
    internal static QuestStateTracker? Tracker;
    internal static MarkerComputer? Markers;
    internal static TrackerState? TrackerPins;

    [HarmonyPostfix]
    private static void Postfix(string _questName)
    {
        Tracker?.OnQuestCompleted(_questName);
        Markers?.MarkDirty();
        TrackerPins?.OnQuestCompleted(_questName);
    }
}
