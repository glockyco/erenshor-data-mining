using AdventureGuide.Graph;
using AdventureGuide.Markers;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves live item bag state by delegating to <see cref="LiveStateTracker"/>.
/// </summary>
public sealed class ItemBagStateResolver : INodeStateResolver
{
    private readonly LiveStateTracker _tracker;

    public ItemBagStateResolver(LiveStateTracker tracker)
    {
        _tracker = tracker;
    }

    public NodeState Resolve(Node node) => _tracker.GetItemBagState(node);
}
