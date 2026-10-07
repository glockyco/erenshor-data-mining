using AdventureGuide.Navigation;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

[HarmonyPatch(typeof(GameData), nameof(GameData.AssignQuest))]
internal static class QuestAssignPatch
{
    internal static QuestStateTracker? Tracker;
    internal static NavigationController? Nav;
    internal static LootScanner? Loot;
    internal static TrackerState? TrackerPins;

    [HarmonyPrefix]
    private static void Prefix(string _questName, out bool __state) =>
        __state = GameData.HasQuest.Contains(_questName);

    [HarmonyPostfix]
    private static void Postfix(string _questName, bool __state)
    {
        if (!QuestMirrorPolicy.WasAdded(__state, GameData.HasQuest.Contains(_questName)))
            return;

        Tracker?.OnQuestAssigned(_questName);
        Nav?.OnGameStateChanged(Tracker?.CurrentZone ?? "");
        Loot?.MarkDirty();

        if (TrackerPins is { Enabled: true, AutoTrackEnabled: true })
            TrackerPins.Track(_questName);
    }
}
