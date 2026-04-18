using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Registers zone-reentry loot chests after SpawnAllCorpses so the
/// resolution pipeline can navigate to chests containing required items.
/// </summary>
[HarmonyPatch(typeof(CorpseDataManager), "SpawnAllCorpses")]
internal static class CorpseChestPatch
{
	internal static LiveStateTracker? LiveState;

	[HarmonyPostfix]
	private static void Postfix()
	{
		LiveState?.OnAllCorpsesSpawned();
	}
}
