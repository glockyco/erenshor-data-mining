using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves door state from the live scene object when available, and falls
/// back to key possession when the door is out of scene.
/// </summary>
public sealed class DoorStateResolver : INodeStateResolver
{
    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;
    private readonly LiveStateTracker _liveState;

    public DoorStateResolver(EntityGraph graph, QuestStateTracker tracker, LiveStateTracker liveState)
    {
        _graph = graph;
        _tracker = tracker;
        _liveState = liveState;
    }

    public NodeState Resolve(Node node)
    {
        var live = _liveState.GetDoorState(node);

        if (node.KeyItemKey == null)
            return live.FoundInScene ? live.State : NodeState.Unlocked;

        string keyName = _graph.GetNode(node.KeyItemKey)?.DisplayName ?? node.KeyItemKey;

        if (live.FoundInScene)
        {
            if (live.State.IsSatisfied)
                return NodeState.Unlocked;

            return _tracker.HasUnlockItem(node.KeyItemKey)
                ? new DoorClosed(keyName)
                : new DoorLocked(keyName);
        }

        return _tracker.HasUnlockItem(node.KeyItemKey)
            ? new DoorClosed(keyName)
            : new DoorLocked(keyName);
    }
}
