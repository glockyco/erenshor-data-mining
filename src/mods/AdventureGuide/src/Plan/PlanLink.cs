using AdventureGuide.Graph;
using AdventureGuide.Plan.Semantics;

namespace AdventureGuide.Plan;

/// <summary>
/// Context-bearing edge in a canonical quest plan. The same canonical entity may
/// be referenced by multiple links with different semantic meaning.
/// </summary>
public sealed class PlanLink
{
    public PlanNodeId FromId { get; }
    public PlanNodeId ToId { get; }
    public PlanStructuralKind StructuralKind { get; }
    public DependencySemantic Semantic { get; }
    public EdgeType? EdgeType { get; }
    public int? Ordinal { get; }
    public int? Quantity { get; }
    public string? Keyword { get; }
    public string? Group { get; }
    public string? Note { get; }

    public PlanLink(
        PlanNodeId fromId,
        PlanNodeId toId,
        DependencySemantic semantic,
        EdgeType? edgeType = null,
        int? ordinal = null,
        int? quantity = null,
        string? keyword = null,
        string? group = null,
        string? note = null)
    {
        FromId = fromId;
        ToId = toId;
        Semantic = semantic;
        StructuralKind = semantic.StructuralKind;
        EdgeType = edgeType;
        Ordinal = ordinal;
        Quantity = quantity;
        Keyword = keyword;
        Group = group;
        Note = note;
    }
}