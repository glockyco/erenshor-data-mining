using AdventureGuide.Graph;

namespace AdventureGuide.Views;

/// <summary>
/// A node in the rendered dependency tree. The universal rendering unit —
/// every UI tree (quest page, item page, character page) is a tree of ViewNodes.
///
/// Created by view builders (QuestViewBuilder, etc.) and consumed by the
/// ViewRenderer which looks up a rendering template by (EdgeType, NodeType).
/// </summary>
public sealed class ViewNode
{
    /// <summary>Graph node key this view node represents.</summary>
    public string NodeKey { get; }

    /// <summary>The edge type that led to this node (null for root).</summary>
    public EdgeType? EdgeType { get; }

    /// <summary>The graph node (cached for rendering — avoids repeated lookups).</summary>
    public Node Node { get; }

    /// <summary>The edge that led to this node (null for root). Carries quantity, keyword, etc.</summary>
    public Edge? Edge { get; }

    /// <summary>Child nodes in the dependency tree.</summary>
    public List<ViewNode> Children { get; } = new();

    /// <summary>True if this node is a pruned cycle back-reference.</summary>
    public bool IsCycleRef { get; set; }

    /// <summary>Whether the UI should show this node's children expanded.</summary>
    public bool DefaultExpanded { get; set; } = true;

    /// <summary>
    /// Zone names where this source node can be found. Populated by the view
    /// builder for source edges (DropsItem, SellsItem, etc.) by collecting unique
    /// zones from spawn point edges. Null for non-source nodes.
    /// </summary>
    public List<string>? SourceZones { get; set; }

    /// <summary>
    /// Effective difficulty level for display. For enemy sources:
    /// max(character level, zone median). For non-combat sources:
    /// zone median. Null when no level data is available.
    /// </summary>
    public int? EffectiveLevel { get; set; }

    public ViewNode(string nodeKey, Node node, EdgeType? edgeType = null, Edge? edge = null)
    {
        NodeKey = nodeKey;
        Node = node;
        EdgeType = edgeType;
        Edge = edge;
    }

    public override string ToString() =>
        EdgeType.HasValue ? $"[{EdgeType.Value}] {Node.DisplayName}" : Node.DisplayName;
}
