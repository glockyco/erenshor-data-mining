using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Position.Resolvers;

/// <summary>
/// Resolves an item bag to its static position. Available bags are actionable;
/// picked-up bags are non-actionable so NAV deprioritises them while markers
/// show "re-enter zone" text. The game recreates all non-unique bags on scene
/// reload, so bags are never permanently gone.
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

        bool actionable = _liveState.GetItemBagState(node) is ItemBagAvailable;
        results.Add(
            new ResolvedPosition(
                node.X.Value,
                node.Y.Value,
                node.Z.Value,
                node.Scene,
                node.Key,
                actionable
            )
        );
    }
}
