using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.State;
using UnityEngine;

namespace AdventureGuide.Navigation.Resolvers;

/// <summary>
/// Resolves an item bag to its static position unless permanently gone.
/// Available bags are actionable; picked-up respawning bags are non-actionable
/// so NAV deprioritises them while markers show respawn timers.
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

        var state = _liveState.GetItemBagState(node);
        if (state is ItemBagGone)
            return;

        bool actionable = state is ItemBagAvailable;
        results.Add(new ResolvedPosition(
            new Vector3(node.X.Value, node.Y.Value, node.Z.Value),
            node.Scene,
            node.Key,
            actionable));
    }
}
