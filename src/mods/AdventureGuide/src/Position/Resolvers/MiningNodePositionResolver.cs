using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Position.Resolvers;

/// <summary>
/// Resolves a mining node to its static position regardless of mined state.
/// Available nodes are actionable; mined nodes are non-actionable so NAV
/// deprioritises them while markers show respawn timers.
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

        bool actionable = _liveState.GetMiningState(node).State is MiningAvailable;
        results.Add(new ResolvedPosition(
            node.X.Value,
            node.Y.Value,
            node.Z.Value,
            node.Scene,
            node.Key,
            actionable));
    }
}
