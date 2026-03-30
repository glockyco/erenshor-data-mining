using AdventureGuide.Graph;

namespace AdventureGuide.Views;

/// <summary>
/// A node in the rendered dependency tree. The universal rendering unit —
/// every UI tree (quest page, item page, character page) is a tree of ViewNodes.
///
/// Created by view builders (QuestViewBuilder, etc.) and consumed by the
/// ViewRenderer which looks up a rendering template by (EdgeType, NodeType).
///
/// Most ViewNodes wrap a real entity graph <see cref="Node"/>. The exception is
/// OR-variant containers (<see cref="IsVariantContainer"/> = true): synthetic
/// grouping nodes that have no backing graph node. Their children are the
/// required-item nodes for one completion variant of a multi-variant quest.
/// Access <see cref="Node"/> only after confirming <c>!IsVariantContainer</c>.
/// </summary>
public sealed class ViewNode
{
    /// <summary>Graph node key this view node represents.</summary>
    public string NodeKey { get; }

    /// <summary>The edge type that led to this node (null for root).</summary>
    public EdgeType? EdgeType { get; }

    // Backing field is nullable; only OR-container nodes have a null Node.
    private readonly Node? _node;

    /// <summary>
    /// The graph node (cached for rendering — avoids repeated lookups).
    /// Throws <see cref="InvalidOperationException"/> when called on an
    /// OR-variant container — check <see cref="IsVariantContainer"/> first.
    /// </summary>
    public Node Node => _node
        ?? throw new InvalidOperationException(
            $"OR-variant container ViewNode '{NodeKey}' has no backing graph node. " +
            "Check IsVariantContainer before accessing Node.");

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

    /// <summary>
    /// When non-null, this node is blocked by an unsatisfied unlock
    /// requirement. The ViewNode is a full expansion of the gating quest's
    /// dependency tree, shown inline as a child sub-tree. Only set when the
    /// node is genuinely unreachable via all paths. Null once satisfied.
    /// </summary>
    public ViewNode? UnlockDependency { get; set; }

    // ── OR-variant container ─────────────────────────────────────────────

    /// <summary>
    /// True when this node is a synthetic OR-variant group container.
    /// Container nodes have no backing graph node; their children are the
    /// required items for one variant of a multi-variant quest.
    /// </summary>
    public bool IsVariantContainer => VariantGroupLabel != null;

    /// <summary>
    /// Human-readable label for this variant group.
    /// Non-null (possibly empty string) marks this as an OR-variant container.
    /// Non-empty = labelled by outcome (e.g. reward item name).
    /// Empty string = unlabelled (same outcome as sibling groups).
    /// </summary>
    public string? VariantGroupLabel { get; set; }

    // ── Constructors ─────────────────────────────────────────────────────

    public ViewNode(string nodeKey, Node node, EdgeType? edgeType = null, Edge? edge = null)
    {
        NodeKey = nodeKey;
        _node = node;
        EdgeType = edgeType;
        Edge = edge;
    }

    // Internal constructor used by CreateVariantContainer only.
    private ViewNode(string nodeKey, EdgeType? edgeType)
    {
        NodeKey = nodeKey;
        _node = null;
        EdgeType = edgeType;
        Edge = null;
    }

    /// <summary>
    /// Create a synthetic OR-variant group container node.
    /// <paramref name="label"/> is shown as a section header when non-empty
    /// (e.g. reward item name for quests where variants produce different items).
    /// Pass an empty string when all sibling groups have the same outcome.
    /// </summary>
    public static ViewNode CreateVariantContainer(
        string nodeKey, string label, EdgeType edgeType)
        => new ViewNode(nodeKey, edgeType) { VariantGroupLabel = label };

    public override string ToString() =>
        IsVariantContainer
            ? $"[VariantGroup] {VariantGroupLabel}"
            : (EdgeType.HasValue ? $"[{EdgeType.Value}] {_node!.DisplayName}" : _node!.DisplayName);
}
