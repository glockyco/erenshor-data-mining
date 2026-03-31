using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves door state by checking whether the player has the required key item
/// either in inventory or on the keyring.
/// </summary>
public sealed class DoorStateResolver : INodeStateResolver
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;

    public DoorStateResolver(EntityGraph graph, QuestStateTracker tracker)
    {
        _graph = graph;
        _tracker = tracker;
    }

    public NodeState Resolve(Node node)
    {
        if (node.KeyItemKey == null)
            return NodeState.Unlocked;

        if (_tracker.HasUnlockItem(node.KeyItemKey))
            return NodeState.Unlocked;

        string keyName = _graph.GetNode(node.KeyItemKey)?.DisplayName ?? node.KeyItemKey;
        return new DoorLocked(keyName);
    }
}
