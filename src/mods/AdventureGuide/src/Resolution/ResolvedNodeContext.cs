using AdventureGuide.Graph;

namespace AdventureGuide.Resolution;

/// <summary>
/// Neutral resolved-node context used by projections and target resolution.
/// Carries graph-node metadata plus edge context without coupling consumers to the
/// lazy detail tree or any UI-specific node type.
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
        int? effectiveLevel = null
    )
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
