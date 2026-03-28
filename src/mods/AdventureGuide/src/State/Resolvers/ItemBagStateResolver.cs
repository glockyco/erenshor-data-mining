using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves item bag state. Currently returns <see cref="NodeState.BagAvailable"/>
/// unconditionally — live bag tracking (scene scanning for picked-up bags)
/// will be added to <c>LiveStateTracker</c> in a future pass.
/// </summary>
public sealed class ItemBagStateResolver : INodeStateResolver
{
    public NodeState Resolve(Node node) => NodeState.BagAvailable;
}
