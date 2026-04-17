using AdventureGuide.Graph;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves door state from the live scene object when available, and falls
/// back to key possession when the door is out of scene.
/// </summary>
public sealed class DoorStateResolver : INodeStateResolver
{
    private readonly CompiledGuideModel _guide;
    private readonly QuestStateTracker _tracker;
    private readonly LiveStateTracker _liveState;

    public DoorStateResolver(
        CompiledGuideModel guide,
        QuestStateTracker tracker,
        LiveStateTracker liveState
    )
    {
        _guide = guide;
        _tracker = tracker;
        _liveState = liveState;
    }

    public NodeState Resolve(Node node)
    {
        var live = _liveState.GetDoorState(node);

        if (node.KeyItemKey == null)
            return live.FoundInScene ? live.State : NodeState.Unlocked;

        string keyName = _guide.GetNode(node.KeyItemKey)?.DisplayName ?? node.KeyItemKey;

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
