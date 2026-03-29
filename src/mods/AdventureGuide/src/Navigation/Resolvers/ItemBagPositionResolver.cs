using AdventureGuide.Graph;
using AdventureGuide.Markers;
using UnityEngine;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves an item bag only while it is currently available in the world.
/// Picked-up / gone bags are excluded from navigation candidates.
/// </summary>
public sealed class ItemBagPositionResolver : IPositionResolver
{
    private readonly LiveStateTracker _liveState;

    public ItemBagPositionResolver(LiveStateTracker liveState)
    {
        _liveState = liveState;
    }

    public void Resolve(Node node, List<ResolvedPosition> results)
    {
        if (node.X is null || node.Y is null || node.Z is null)
            return;

        if (!_liveState.GetItemBagState(node).IsSatisfied)
            return;

        results.Add(new ResolvedPosition(
            new Vector3(node.X.Value, node.Y.Value, node.Z.Value),
            node.Scene,
            node.Key));
    }
}
