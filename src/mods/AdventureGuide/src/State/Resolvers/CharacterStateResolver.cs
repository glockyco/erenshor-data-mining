using AdventureGuide.Graph;
using AdventureGuide.Markers;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves live character state (alive, dead with timer, night-locked, etc.)
/// by delegating to <see cref="LiveStateTracker"/>.
/// </summary>
public sealed class CharacterStateResolver : INodeStateResolver
{
    private readonly LiveStateTracker _tracker;

    public CharacterStateResolver(LiveStateTracker tracker)
    {
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        var info = _tracker.GetCharacterState(node);
        return info.State;
    }
}
