using AdventureGuide.Graph;

namespace AdventureGuide.State.Resolvers;

/// <summary>
/// Resolves zone line accessibility from incoming <see cref="EdgeType.UnlocksZoneLine"/>
/// edges using the shared unlock evaluator.
/// </summary>
public sealed class ZoneLineStateResolver : INodeStateResolver
{
    private readonly UnlockEvaluator _unlocks;

    public ZoneLineStateResolver(UnlockEvaluator unlocks)
    {
        _unlocks = unlocks;
    }

    public NodeState Resolve(Node node)
    {
        var evaluation = _unlocks.Evaluate(node);
        return evaluation.IsUnlocked
            ? NodeState.Accessible
            : new ZoneLineLocked(evaluation.Reason ?? "Locked");
    }
}
