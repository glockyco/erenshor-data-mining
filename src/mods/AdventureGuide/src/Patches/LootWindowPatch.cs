using System.Reflection;
using AdventureGuide.Incremental;
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

	[HarmonyPostfix]
	private static void Postfix(LootWindow __instance)
	{
		if (LiveState == null || Engine == null)
			return;

		TryHandleLootClose<LootTable, NPC>(
			ParentField?.GetValue(__instance),
			static parent => parent != null,
			static parent => parent.GetComponent<NPC>(),
			LiveState.OnCorpseLooted,
			facts => Engine.InvalidateFacts(facts),
			facts => ZoneRouter?.ObserveInvalidation(facts)
		);
	}

	internal static bool TryHandleLootClose<TParent, TNpc>(
		object? parentCandidate,
		Func<TParent, bool> canInspectParent,
		Func<TParent, TNpc?> getNpc,
		Func<TNpc, ChangeSet> onCorpseLooted,
		Action<IReadOnlyCollection<FactKey>> invalidateFacts,
		Action<IReadOnlyCollection<FactKey>>? observeInvalidation
	)
		where TParent : class
		where TNpc : class
	{
		if (parentCandidate is not TParent parent)
			return false;

		if (!canInspectParent(parent))
			return false;

		var npc = getNpc(parent);
		if (npc == null)
			return false;

		var change = onCorpseLooted(npc);
		if (!change.HasMeaningfulChanges)
			return true;

		invalidateFacts(change.ChangedFacts);
		observeInvalidation?.Invoke(change.ChangedFacts);
		return true;
	}
}
