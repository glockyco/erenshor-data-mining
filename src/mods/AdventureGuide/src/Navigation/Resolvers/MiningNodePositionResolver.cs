using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves a mining node only when it is currently available. Mined nodes are
/// excluded from navigation candidates so selection can move to another live node.
/// </summary>
public sealed class MiningNodePositionResolver : IPositionResolver
{
    private readonly LiveStateTracker _liveState;

    public MiningNodePositionResolver(LiveStateTracker liveState)
    {
        _liveState = liveState;
    }

    public void Resolve(Node node, List<ResolvedPosition> results)
    {
        if (node.X is null || node.Y is null || node.Z is null)
            return;

        if (_liveState.GetMiningState(node).State is not MiningAvailable)
            return;

        results.Add(new ResolvedPosition(
            new Vector3(node.X.Value, node.Y.Value, node.Z.Value),
            node.Scene,
            node.Key));
    }
}
