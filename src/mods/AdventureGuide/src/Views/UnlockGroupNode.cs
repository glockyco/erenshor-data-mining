
namespace AdventureGuide.Views;

/// <summary>
/// Synthetic container for an AND-group of unlock requirements.
/// <para>
/// Unlike <see cref="VariantGroupNode"/>, these children are all required. The
/// node has no backing graph entity; it only groups the blocking source trees
/// that must all be satisfied before the parent becomes actionable.
/// </para>
/// </summary>
public sealed class UnlockGroupNode : ViewNode
{
    public string Label { get; }

    public UnlockGroupNode(string nodeKey, string label)
        : base(nodeKey, edgeType: null, edge: null)
    {
        Label = label;
    }

    public override string ToString() => $"[UnlockGroup: {Label}]";
}
