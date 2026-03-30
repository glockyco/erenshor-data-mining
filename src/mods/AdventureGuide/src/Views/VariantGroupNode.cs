using AdventureGuide.Graph;

namespace AdventureGuide.Views;

/// <summary>
/// A synthetic OR-group container in the view tree. Represents one completion
/// variant of a multi-variant quest (same DBName, different required items per
/// ScriptableObject variant).
///
/// Has no backing entity graph node. Its <see cref="ViewNode.Children"/> are
/// the <see cref="EntityViewNode"/>s for the items required to complete this
/// variant. When a quest has N distinct variant groups, N sibling
/// <see cref="VariantGroupNode"/>s appear as consecutive children of the quest
/// node; the player completes exactly one, not all.
///
/// <see cref="Label"/> is non-empty when variants produce different reward items
/// (e.g. Malaroth Food good vs. bad recipe). Empty when all groups lead to the
/// same outcome (e.g. Disarming the Sivakayans — different weapons, same reward).
///
/// <see cref="FrontierComputer.ComputeFrontier"/> treats these as transparent
/// containers — it recurses into children and never adds a
/// <see cref="VariantGroupNode"/> to the frontier result.
/// </summary>
public sealed class VariantGroupNode : ViewNode
{
    /// <summary>
    /// Human-readable label for this variant group.
    /// Non-empty when this group's outcome (reward item) differs from siblings.
    /// Empty when all groups lead to the same outcome.
    /// </summary>
    public string Label { get; }

    /// <summary>True when <see cref="Label"/> is non-empty.</summary>
    public bool HasLabel => Label.Length > 0;

    public VariantGroupNode(string nodeKey, string label, EdgeType edgeType)
        : base(nodeKey, edgeType, edge: null)
    {
        Label = label;
    }

    public override string ToString() =>
        HasLabel ? $"[VariantGroup: {Label}]" : "[VariantGroup]";
}
