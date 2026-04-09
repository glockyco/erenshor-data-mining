using AdventureGuide.Graph;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.State;

/// <summary>
/// Evaluates incoming unlock edges for blocked content such as zone lines and
/// characters.
/// <para>
/// Unlock semantics are target-specific: the target type chooses which incoming
/// edge type represents its unlock requirements, while each source node is
/// evaluated using the live rule that matches that source type.
/// </para>
/// <para>
/// Item unlock sources are satisfied by possession in inventory OR keyring.
/// Other source types use their normal live <see cref="NodeState"/> through
/// <see cref="GameState"/>.
/// </para>
/// </summary>
public sealed class UnlockEvaluator
{
    private readonly CompiledGuideModel _guide;
    private readonly GameState _state;
    private readonly QuestStateTracker _tracker;

    public UnlockEvaluator(CompiledGuideModel guide, GameState state, QuestStateTracker tracker)
    {
        _guide = guide;
        _state = state;
        _tracker = tracker;
    }

    public UnlockEvaluation Evaluate(Node target)
    {
        if (target == null)
            throw new ArgumentNullException(nameof(target));

        return TryGetUnlockEdgeType(target.Type, out var edgeType)
            ? Evaluate(target.Key, edgeType)
            : UnlockEvaluation.Unlocked;
    }

    public UnlockEvaluation Evaluate(string targetKey, EdgeType edgeType)
    {
        var unlockEdges = _guide.InEdges(targetKey, edgeType);
        if (unlockEdges.Count == 0)
            return UnlockEvaluation.Unlocked;

        List<Edge>? unconditional = null;
        Dictionary<string, List<Edge>>? groups = null;

        for (int i = 0; i < unlockEdges.Count; i++)
        {
            var edge = unlockEdges[i];
            if (edge.Group == null)
            {
                unconditional ??= new List<Edge>();
                unconditional.Add(edge);
                continue;
            }

            groups ??= new Dictionary<string, List<Edge>>(StringComparer.Ordinal);
            if (!groups.TryGetValue(edge.Group, out var list))
            {
                list = new List<Edge>();
                groups[edge.Group] = list;
            }

            list.Add(edge);
        }

        bool unconditionalSatisfied = IsGroupSatisfied(unconditional);
        if (unconditionalSatisfied)
        {
            if (groups == null)
                return UnlockEvaluation.Unlocked;

            foreach (var group in groups.Values)
            {
                if (IsGroupSatisfied(group))
                    return UnlockEvaluation.Unlocked;
            }
        }

        var blockingEdges = SelectBlockingEdges(unconditional, unconditionalSatisfied, groups);
        var blockingSources = new List<Node>(blockingEdges.Count);
        var labels = new List<string>(blockingEdges.Count);

        for (int i = 0; i < blockingEdges.Count; i++)
        {
            var source = _guide.GetNode(blockingEdges[i].Source);
            if (source == null || IsSourceSatisfied(source))
                continue;

            blockingSources.Add(source);
            labels.Add(source.DisplayName);
        }

        if (blockingSources.Count == 0)
            return new UnlockEvaluation(false, Array.Empty<Node>(), "Locked");

        return new UnlockEvaluation(false, blockingSources, "Requires: " + string.Join(", ", labels));
    }

    public string? GetRequirementReason(string targetKey)
    {
        var target = _guide.GetNode(targetKey);
        if (target == null)
            return null;

        var evaluation = Evaluate(target);
        return evaluation.IsUnlocked ? null : evaluation.Reason;
    }

    public static bool TryGetUnlockEdgeType(NodeType targetType, out EdgeType edgeType)
    {
        switch (targetType)
        {
            case NodeType.ZoneLine:
                edgeType = EdgeType.UnlocksZoneLine;
                return true;
            case NodeType.Character:
                edgeType = EdgeType.UnlocksCharacter;
                return true;
            case NodeType.Door:
                edgeType = EdgeType.UnlocksDoor;
                return true;
            default:
                edgeType = default;
                return false;
        }
    }

    private bool IsGroupSatisfied(List<Edge>? edges)
    {
        if (edges == null || edges.Count == 0)
            return true;

        for (int i = 0; i < edges.Count; i++)
        {
            var source = _guide.GetNode(edges[i].Source);
            if (source == null || !IsSourceSatisfied(source))
                return false;
        }

        return true;
    }

    private List<Edge> SelectBlockingEdges(
        List<Edge>? unconditional,
        bool unconditionalSatisfied,
        Dictionary<string, List<Edge>>? groups)
    {
        if (!unconditionalSatisfied && unconditional != null)
            return unconditional;

        if (groups != null)
        {
            foreach (var group in groups.Values)
            {
                if (!IsGroupSatisfied(group))
                    return group;
            }
        }

        return new List<Edge>();
    }

    private bool IsSourceSatisfied(Node source)
    {
        return source.Type == NodeType.Item
            ? _tracker.HasUnlockItem(source.Key)
            : _state.GetState(source.Key).IsSatisfied;
    }
}

public sealed class UnlockEvaluation
{
    public static readonly UnlockEvaluation Unlocked = new(true, Array.Empty<Node>(), null);

    public bool IsUnlocked { get; }
    public IReadOnlyList<Node> BlockingSources { get; }
    public string? Reason { get; }

    public UnlockEvaluation(bool isUnlocked, IReadOnlyList<Node> blockingSources, string? reason)
    {
        IsUnlocked = isUnlocked;
        BlockingSources = blockingSources;
        Reason = reason;
    }
}
