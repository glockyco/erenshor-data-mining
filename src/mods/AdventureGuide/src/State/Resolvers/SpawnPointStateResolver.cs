using AdventureGuide.Graph;
using AdventureGuide.Markers;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves live spawn point state (alive, dead with respawn timer,
/// disabled, night-locked, quest-gated) by delegating to <see cref="LiveStateTracker"/>.
/// </summary>
public sealed class SpawnPointStateResolver : INodeStateResolver
{
    private readonly LiveStateTracker _tracker;

    public SpawnPointStateResolver(LiveStateTracker tracker)
    {
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        var info = _tracker.GetSpawnState(node);
        return info.State;
    }
}
