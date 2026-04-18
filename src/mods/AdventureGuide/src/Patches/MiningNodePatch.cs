using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Notifies live-state and guide systems when a mining node changes so marker
/// and navigation invalidation can stay source-local.
/// </summary>
internal static class MiningNodePatch
{
	internal static LiveStateTracker? LiveState;

	[HarmonyPatch(typeof(MiningNode), nameof(MiningNode.Mine))]
	[HarmonyPostfix]
	private static void MinePostfix(MiningNode __instance)
	{
		NotifyChanged(__instance);
	}

	[HarmonyPatch(typeof(MiningNode), "Update")]
	[HarmonyPrefix]
	private static void UpdatePrefix(MiningNode __instance, out bool __state)
	{
		__state = IsAvailable(__instance);
	}

	[HarmonyPatch(typeof(MiningNode), "Update")]
	[HarmonyPostfix]
	private static void UpdatePostfix(MiningNode __instance, bool __state)
	{
		if (__state == IsAvailable(__instance))
			return;

		NotifyChanged(__instance);
	}

	private static void NotifyChanged(MiningNode miningNode)
	{
		LiveState?.OnMiningChanged(miningNode);
	}

	private static bool IsAvailable(MiningNode miningNode) =>
		miningNode.MyRender == null || miningNode.MyRender.enabled;
}
