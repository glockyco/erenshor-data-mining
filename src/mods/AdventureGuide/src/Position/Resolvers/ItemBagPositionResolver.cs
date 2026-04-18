using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Position.Resolvers;

/// <summary>
/// Resolves an item bag to its static position. Available bags are actionable;
/// picked-up bags are non-actionable so NAV deprioritises them while markers
/// show "re-enter zone" text. The game recreates all non-unique bags on scene
/// reload, so bags are never permanently gone.
/// </summary>
internal sealed class ItemBagPositionResolver : LiveStateBackedPositionResolver
{
	public ItemBagPositionResolver(LiveStateTracker liveState)
		: base(liveState) { }

	protected override bool? TryGetCachedAvailability(Node node) =>
		LiveState.TryGetCachedItemBagAvailability(node, out bool available) ? available : null;

	protected override bool QueryLiveAvailability(Node node) =>
		LiveState.GetItemBagState(node) is ItemBagAvailable;
}
