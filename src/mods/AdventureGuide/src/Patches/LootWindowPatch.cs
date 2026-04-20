using System.Reflection;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation;
using AdventureGuide.Position;
using AdventureGuide.State;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>
/// Invalidates source-state facts when corpse loot is finalized through the
/// loot window.
/// </summary>
[HarmonyPatch(typeof(LootWindow), nameof(LootWindow.CloseWindow))]
internal static class LootWindowCloseWindowPatch
{
	private static readonly FieldInfo? ParentField = typeof(LootWindow).GetField(
		"parent",
		BindingFlags.Instance | BindingFlags.NonPublic
	);

	internal static LiveStateTracker? LiveState;
	internal static Engine<FactKey>? Engine;
	internal static ZoneRouter? ZoneRouter;
	internal static NavigationTargetSelector? Selector;
	[HarmonyPostfix]
	private static void Postfix(LootWindow __instance)
	{
		if (LiveState == null || Engine == null)
			return;

		if (ParentField?.GetValue(__instance) is not LootTable parent)
			return;

		var npc = parent.GetComponent<NPC>();
		if (npc == null)
			return;

		var change = LiveState.OnCorpseLooted(npc);
		if (!change.HasMeaningfulChanges)
		    return;

		Selector?.InvalidateTargets();
		Engine.InvalidateFacts(change.ChangedFacts);
		ZoneRouter?.ObserveInvalidation(change.ChangedFacts);	}
}
