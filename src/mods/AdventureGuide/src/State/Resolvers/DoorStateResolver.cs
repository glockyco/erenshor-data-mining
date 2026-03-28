using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves door state by checking whether the player has the required key item
/// in inventory via <see cref="QuestStateTracker.CountItem"/>.
/// Doors with no key requirement are always unlocked.
/// </summary>
public sealed class DoorStateResolver : INodeStateResolver
{
    private readonly QuestStateTracker _tracker;

    public DoorStateResolver(QuestStateTracker tracker)
    {
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        if (node.KeyItemKey == null)
            return NodeState.Unlocked;

        int count = _tracker.CountItem(node.KeyItemKey);
        return count > 0 ? NodeState.Unlocked : new DoorLocked(node.KeyItemKey);
    }
}
