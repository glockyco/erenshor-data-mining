using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Position.Resolvers;

/// <summary>
/// Position resolver that reads actionability from a
/// <see cref="LiveStateTracker"/> position-keyed cache and falls back to a live
/// query on cache miss. Construction supplies both callbacks so the same
/// machinery handles mining nodes, item bags, and test stubs without a
/// subclass hierarchy.
/// </summary>
internal sealed class LiveStateBackedPositionResolver : IPositionResolver
{
	private readonly Func<Node, bool?> _tryGetCachedAvailability;
	private readonly Func<Node, bool> _queryLiveAvailability;

	public LiveStateBackedPositionResolver(
		Func<Node, bool?> tryGetCachedAvailability,
		Func<Node, bool> queryLiveAvailability
	)
	{
		_tryGetCachedAvailability = tryGetCachedAvailability;
		_queryLiveAvailability = queryLiveAvailability;
	}

	public void Resolve(Node node, List<ResolvedPosition> results)
	{
		if (node.X is null || node.Y is null || node.Z is null)
			return;

		bool actionable = _tryGetCachedAvailability(node) ?? _queryLiveAvailability(node);
		results.Add(
			new ResolvedPosition(
				node.X.Value,
				node.Y.Value,
				node.Z.Value,
				node.Scene,
				node.Key,
				actionable
			)
		);
	}

	/// <summary>Resolver for mining nodes: cache → live state lookup.</summary>
	public static LiveStateBackedPositionResolver MiningNode(LiveStateTracker liveState) =>
		new(
			tryGetCachedAvailability: node =>
				liveState.TryGetCachedMiningAvailability(node, out bool available) ? available : null,
			queryLiveAvailability: node =>
				liveState.GetMiningState(node).State is MiningAvailable
		);

	/// <summary>Resolver for item bags: cache → live state lookup.</summary>
	public static LiveStateBackedPositionResolver ItemBag(LiveStateTracker liveState) =>
		new(
			tryGetCachedAvailability: node =>
				liveState.TryGetCachedItemBagAvailability(node, out bool available) ? available : null,
			queryLiveAvailability: node =>
				liveState.GetItemBagState(node) is ItemBagAvailable
		);
}
