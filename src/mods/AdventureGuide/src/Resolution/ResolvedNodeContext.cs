using AdventureGuide.Graph;

namespace AdventureGuide.Resolution;

/// <summary>
/// Neutral resolved-node context used by projections and target resolution.
/// Replaces the old dependency on EntityViewNode so canonical-plan consumers can
/// pass edge context without requiring a visual tree node.
/// </summary>
public sealed class ResolvedNodeContext
{
    public string NodeKey { get; }
    public Node Node { get; }
    public EdgeType? EdgeType { get; }
    public int? Quantity { get; }
    public string? Keyword { get; }
    public IReadOnlyList<string>? SourceZones { get; }
    public int? EffectiveLevel { get; }

    public ResolvedNodeContext(
        string nodeKey,
        Node node,
        EdgeType? edgeType = null,
        int? quantity = null,
        string? keyword = null,
        IReadOnlyList<string>? sourceZones = null,
        int? effectiveLevel = null)
    {
        NodeKey = nodeKey;
        Node = node;
        EdgeType = edgeType;
        Quantity = quantity;
        Keyword = keyword;
        SourceZones = sourceZones;
        EffectiveLevel = effectiveLevel;
    }
}