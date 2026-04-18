using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Position.Resolvers;

/// <summary>
/// Shared base for position resolvers that read availability from a
/// <see cref="LiveStateTracker"/> position-keyed cache and fall back to a live
/// query on cache miss.
/// </summary>
internal abstract class LiveStateBackedPositionResolver : IPositionResolver
{
	protected readonly LiveStateTracker LiveState;

	protected LiveStateBackedPositionResolver(LiveStateTracker liveState)
	{
		LiveState = liveState;
	}

	public void Resolve(Node node, List<ResolvedPosition> results)
	{
		if (node.X is null || node.Y is null || node.Z is null)
			return;

		bool actionable = TryGetCachedAvailability(node) ?? QueryLiveAvailability(node);
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

	protected abstract bool? TryGetCachedAvailability(Node node);

	protected abstract bool QueryLiveAvailability(Node node);
}
