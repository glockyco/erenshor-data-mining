using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

[HarmonyPatch(typeof(GameData), nameof(GameData.AssignQuest))]
internal static class QuestAssignPatch
{
	internal static QuestStateTracker? Tracker;
	internal static TrackerState? TrackerPins;

	[HarmonyPostfix]
	private static void Postfix(string _questName)
	{
		Tracker?.OnQuestAssigned(_questName);

		if (TrackerPins is { Enabled: true, AutoTrackEnabled: true })
			TrackerPins.Track(_questName);
	}
}
