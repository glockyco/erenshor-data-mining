using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves live mining node state (available or mined with respawn timer)
/// by delegating to <see cref="LiveStateTracker"/>.
/// </summary>
public sealed class MiningNodeStateResolver : INodeStateResolver
{
    private readonly LiveStateTracker _tracker;

    public MiningNodeStateResolver(LiveStateTracker tracker)
    {
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        var info = _tracker.GetMiningState(node);
        return info.State;
    }
}
