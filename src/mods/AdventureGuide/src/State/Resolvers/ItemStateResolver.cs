using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves item node state as an inventory count.
/// The node key IS the item stable key (e.g. "item:luminstone").
/// </summary>
public sealed class ItemStateResolver : INodeStateResolver
{
    private readonly QuestStateTracker _tracker;

    public ItemStateResolver(QuestStateTracker tracker)
    {
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        int count = _tracker.CountItem(node.Key);
        return new ItemCount(count);
    }
}
