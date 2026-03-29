using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;

namespace AdventureGuide.Frontier;

/// <summary>
/// Formats frontier ViewNodes into player-facing action text.
///
/// Two assembly patterns, same underlying logic:
/// <list type="bullet">
///   <item><see cref="FormatAction"/>: action only, no target name.
///     For marker sub-text where the marker IS the target.
///     Example: "Kill", "Say 'tomb'", "2/5 Dragon Scale"</item>
///   <item><see cref="FormatSummary"/>: action + target name.
///     For tracker overlay and arrow labels.
///     Example: "Kill Grizzlemaw", "Say 'tomb' to Kedon", "Dragon Scale (2/5)"</item>
/// </list>
///
/// The detail panel (ViewRenderer) uses its own verbose format with colons
/// and em-dashes because tree nodes need different readability than glanceable
/// overlay text.
/// </summary>
public static class ActionTextFormatter
{
    // ── Marker sub-text: action only ────────────────────────────────────

    /// <summary>
    /// Terse action without target name. The marker position identifies the target.
    /// </summary>
    public static string FormatAction(EdgeType? edgeType, Edge? edge)
    {
        return edgeType switch
        {
            EdgeType.StepTalk when edge?.Keyword != null => $"Say '{edge.Keyword}'",
            EdgeType.StepTalk => "Talk to",
            EdgeType.StepKill when edge?.Quantity is > 1 => $"Kill ({edge.Quantity})",
            EdgeType.StepKill => "Kill",
            EdgeType.StepShout when edge?.Keyword != null => $"Shout '{edge.Keyword}'",
            EdgeType.StepShout => "Shout near",
            EdgeType.StepTravel => "Travel to",
            EdgeType.StepRead => "Read",
            EdgeType.CompletedBy when edge?.Keyword != null => $"Say '{edge.Keyword}'",
            EdgeType.CompletedBy => "Turn in",
            EdgeType.AssignedBy when edge?.Keyword != null => $"Say '{edge.Keyword}'",
            EdgeType.AssignedBy => "Talk to",
            EdgeType.GivesItem when edge?.Keyword != null => $"Say '{edge.Keyword}'",
            EdgeType.GivesItem => "Talk to",
            EdgeType.SellsItem => "Buy",
            EdgeType.DropsItem => "Kill",
            EdgeType.YieldsItem => "Gather",
            _ => "Talk to",
        };
    }

    // ── Tracker / arrow: action + target ────────────────────────────────

    /// <summary>
    /// Compact action + target name. For tracker overlay lines and arrow labels.
    /// Items show have/need progress when a tracker is provided.
    /// </summary>
    public static string FormatSummary(
        ViewNode frontierNode, QuestStateTracker? tracker = null)
    {
        var edge = frontierNode.Edge;
        var node = frontierNode.Node;
        string name = node.DisplayName;

        return frontierNode.EdgeType switch
        {
            EdgeType.StepTalk when edge?.Keyword != null
                => $"Say '{edge.Keyword}' to {name}",
            EdgeType.StepTalk => $"Talk to {name}",

            EdgeType.StepKill when edge?.Quantity is > 1
                => $"Kill {name} ({edge.Quantity})",
            EdgeType.StepKill => $"Kill {name}",

            EdgeType.StepShout when edge?.Keyword != null
                => $"Shout '{edge.Keyword}' near {name}",
            EdgeType.StepShout => $"Shout near {name}",

            EdgeType.StepTravel => $"Go to {name}",
            EdgeType.StepRead => $"Read {name}",

            EdgeType.CompletedBy when edge?.Keyword != null
                => $"Say '{edge.Keyword}' to {name}",
            EdgeType.CompletedBy => $"Turn in to {name}",

            EdgeType.AssignedBy when edge?.Keyword != null
                => $"Say '{edge.Keyword}' to {name}",
            EdgeType.AssignedBy => FormatAssignmentSummary(frontierNode),

            EdgeType.RequiresItem => FormatItemSummary(name, edge, frontierNode.NodeKey, tracker),
            EdgeType.RequiresQuest => $"Complete {name}",

            _ => name,
        };
    }

    private static string FormatItemSummary(
        string itemName, Edge? edge, string nodeKey, QuestStateTracker? tracker)
    {
        int need = edge?.Quantity ?? 1;
        if (need <= 1)
            return $"Collect {itemName}";

        if (tracker != null)
        {
            int have = tracker.CountItem(nodeKey);
            return $"{itemName} ({have}/{need})";
        }

        return $"Collect {itemName} (\u00d7{need})";
    }

    private static string FormatAssignmentSummary(ViewNode node)
    {
        string name = node.Node.DisplayName;
        return node.Node.Type switch
        {
            Graph.NodeType.Item => $"Read {name}",
            Graph.NodeType.Zone => $"Go to {name}",
            Graph.NodeType.Quest => $"Complete {name}",
            _ => $"Talk to {name}",
        };
    }
}
