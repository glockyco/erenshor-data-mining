using AdventureGuide.Graph;
using AdventureGuide.State;

namespace AdventureGuide.Tests.Helpers;

internal sealed class TestResolutionLiveState : IResolutionLiveState
{
    public bool CorpseContainsItem(Node spawnNode, string itemStableKey) => false;

    public bool TryGetCorpsePositionWithItem(
        Node spawnNode,
        string itemStableKey,
        out LiveChestPosition position
    )
    {
        position = default;
        return false;
    }

    public IEnumerable<LiveChestPosition> GetRotChestPositionsWithItem(string itemStableKey)
    {
        yield break;
    }
}
