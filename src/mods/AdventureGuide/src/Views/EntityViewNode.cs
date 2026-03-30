using AdventureGuide.Graph;

namespace AdventureGuide.Views;

/// <summary>
/// A view node backed by a real entity graph <see cref="Node"/>.
///
/// Every tree entry that represents something in the game world (quest,
/// character, item, zone, mining node, etc.) is an <see cref="EntityViewNode"/>.
///
/// All frontier results from <see cref="FrontierComputer.ComputeFrontier"/> are
/// <see cref="EntityViewNode"/> instances; so are the goal and target nodes in
/// <see cref="ResolvedViewPosition"/> and <see cref="ResolvedQuestTarget"/>.
/// </summary>
public sealed class EntityViewNode : ViewNode
{
    /// <summary>The entity graph node this view node represents.</summary>
    public Node Node { get; }

    public EntityViewNode(string nodeKey, Node node,
        EdgeType? edgeType = null, Edge? edge = null)
        : base(nodeKey, edgeType, edge)
    {
        Node = node;
    }

    public override string ToString() =>
        EdgeType.HasValue
            ? $"[{EdgeType.Value}] {Node.DisplayName}"
            : Node.DisplayName;
}
