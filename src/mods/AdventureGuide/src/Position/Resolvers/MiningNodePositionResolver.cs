using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Position.Resolvers;

/// <summary>
/// Resolves a mining node to its static position regardless of mined state.
/// Available nodes are actionable; mined nodes are non-actionable so NAV
/// deprioritises them while markers show respawn timers.
/// </summary>
internal sealed class MiningNodePositionResolver : LiveStateBackedPositionResolver
{
	public MiningNodePositionResolver(LiveStateTracker liveState)
		: base(liveState) { }

	protected override bool? TryGetCachedAvailability(Node node) =>
		LiveState.TryGetCachedMiningAvailability(node, out bool available) ? available : null;

	protected override bool QueryLiveAvailability(Node node) =>
		LiveState.GetMiningState(node).State is MiningAvailable;
}
