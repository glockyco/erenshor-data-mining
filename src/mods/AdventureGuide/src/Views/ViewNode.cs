using AdventureGuide.Graph;

namespace AdventureGuide.Views;

/// <summary>
/// Abstract base for all nodes in the rendered dependency tree.
///
/// Three concrete types:
/// <list type="bullet">
///   <item><see cref="EntityViewNode"/> — wraps a real entity graph <see cref="Node"/>.</item>
///   <item><see cref="VariantGroupNode"/> — a synthetic OR-group container for one
///     completion variant of a multi-variant quest. Has no backing graph node.</item>
///   <item><see cref="UnlockGroupNode"/> — a synthetic AND-group container for
///     multiple simultaneous unlock requirements.</item>
/// </list>
///
/// Every surface (renderer, frontier computer, position collector) must
/// pattern-match on the concrete type before accessing entity-specific data.
/// <see cref="Frontier.FrontierComputer.ComputeFrontier"/> always returns
/// <see cref="EntityViewNode"/> instances — structural containers are never frontier
/// leaves.
/// </summary>
public abstract class ViewNode
{
    /// <summary>Graph node key this view node represents.</summary>
    public string NodeKey { get; }

    /// <summary>The edge type that led to this node (null for root).</summary>
    public EdgeType? EdgeType { get; }

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
    /// When non-null, this node is blocked by an unsatisfied unlock requirement.
    /// The subtree may be a single entity source or a synthetic AND-group container
    /// when multiple requirements must all be satisfied. Null once unlocked.
    /// </summary>
    public ViewNode? UnlockDependency { get; set; }

    protected ViewNode(string nodeKey, EdgeType? edgeType, Edge? edge)
    {
        NodeKey = nodeKey;
        EdgeType = edgeType;
        Edge = edge;
    }
}
