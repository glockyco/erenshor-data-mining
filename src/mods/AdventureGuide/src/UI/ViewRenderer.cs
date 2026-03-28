using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Single recursive tree renderer for ViewNode trees. Replaces QuestDetailPanel's
/// per-type rendering with a data-driven approach: each (EdgeType, NodeType)
/// combination maps to a rendering pattern.
///
/// Adding a new edge or node type = adding a case to the render switch.
/// No separate DrawSteps/DrawPrereqs/DrawRewards methods.
/// </summary>
public sealed class ViewRenderer
{
    private readonly EntityGraph _graph;
    private readonly GameState _state;
    private readonly NavigationSet _navSet;

    public ViewRenderer(EntityGraph graph, GameState state, NavigationSet navSet)
    {
        _graph = graph;
        _state = state;
        _navSet = navSet;
    }

    /// <summary>Render a full quest view tree.</summary>
    public void Draw(ViewNode? root)
    {
        if (root == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("Select a quest from the list.");
            ImGui.PopStyleColor();
            return;
        }

        // Header
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(root.Node.DisplayName);
        ImGui.PopStyleColor();

        // Description
        if (!string.IsNullOrEmpty(root.Node.Description))
        {
            ImGui.Spacing();
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped(root.Node.Description);
            ImGui.PopStyleColor();
        }

        // Quest state badge
        DrawQuestBadge(root.NodeKey);

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();

        // Children: the dependency tree
        foreach (var child in root.Children)
            DrawNode(child, 0);
    }

    // ── Recursive node renderer ─────────────────────────────────────────

    private void DrawNode(ViewNode node, int depth)
    {
        if (node.IsCycleRef)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped($"  ↻ {node.Node.DisplayName} (see above)");
            ImGui.PopStyleColor();
            return;
        }

        // Build the label from edge type + node data
        string label = FormatLabel(node);
        uint color = GetNodeColor(node);
        bool hasChildren = node.Children.Count > 0;

        // State indicator (checkmark for satisfied nodes)
        var nodeState = _state.GetState(node.NodeKey);
        string statePrefix = nodeState.IsSatisfied ? "✓ " : "";

        if (hasChildren)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, color);
            bool open = ImGui.TreeNodeEx(
                $"{statePrefix}{label}###{node.NodeKey}_{depth}",
                node.DefaultExpanded ? ImGuiTreeNodeFlags.DefaultOpen : ImGuiTreeNodeFlags.None);
            ImGui.PopStyleColor();

            // NAV button on the same line
            DrawNavButton(node);

            if (open)
            {
                foreach (var child in node.Children)
                    DrawNode(child, depth + 1);
                ImGui.TreePop();
            }
        }
        else
        {
            // Leaf node — no tree expander
            ImGui.PushStyleColor(ImGuiCol.Text, color);
            ImGui.BulletText($"{statePrefix}{label}");
            ImGui.PopStyleColor();

            DrawNavButton(node);
        }
    }

    // ── Label formatting ────────────────────────────────────────────────

    private static string FormatLabel(ViewNode node)
    {
        var edge = node.Edge;
        var n = node.Node;
        string name = n.DisplayName;

        if (node.EdgeType == null)
            return name;

        string prefix = node.EdgeType.Value switch
        {
            EdgeType.RequiresQuest => "Requires: ",
            EdgeType.RequiresItem => FormatQuantity("Obtain: ", name, edge?.Quantity),
            EdgeType.StepTalk => FormatKeyword("Talk to ", name, edge?.Keyword),
            EdgeType.StepKill => $"Kill: {name}",
            EdgeType.StepTravel => $"Travel to: {name}",
            EdgeType.StepShout => FormatKeyword("Shout at ", name, edge?.Keyword),
            EdgeType.StepRead => $"Read: {name}",
            EdgeType.CompletedBy => FormatKeyword("Turn in to ", name, edge?.Keyword),
            EdgeType.AssignedBy => FormatKeyword("Talk to ", name, edge?.Keyword),
            EdgeType.CraftedFrom => $"Crafted via: {name}",
            EdgeType.RequiresMaterial => FormatQuantity("Ingredient: ", name, edge?.Quantity),
            EdgeType.DropsItem => FormatChance($"Drops from: {name}", edge?.Chance),
            EdgeType.SellsItem => $"Vendor: {name}",
            EdgeType.GivesItem => FormatKeyword("Talk to ", name, edge?.Keyword),
            EdgeType.YieldsItem => $"Gathered from: {name}",
            EdgeType.RewardsItem => $"Quest reward: {name}",
            _ => $"[{node.EdgeType.Value}] {name}",
        };

        // Append zone context if available
        if (n.Zone != null && !prefix.Contains(n.Zone))
            prefix += $" ({n.Zone})";

        return prefix;
    }

    private static string FormatQuantity(string prefix, string name, int? quantity)
    {
        if (quantity.HasValue && quantity.Value > 1)
            return $"{prefix}{name} (×{quantity.Value})";
        return $"{prefix}{name}";
    }

    private static string FormatKeyword(string prefix, string name, string? keyword)
    {
        if (!string.IsNullOrEmpty(keyword))
            return $"{prefix}{name} — say \"{keyword}\"";
        return $"{prefix}{name}";
    }

    private static string FormatChance(string text, float? chance)
    {
        if (chance.HasValue && chance.Value < 1.0f)
            return $"{text} ({chance.Value:P0})";
        return text;
    }

    // ── Colors ──────────────────────────────────────────────────────────

    private uint GetNodeColor(ViewNode node)
    {
        var nodeState = _state.GetState(node.NodeKey);

        if (nodeState.IsSatisfied)
            return Theme.QuestCompleted;

        return node.EdgeType switch
        {
            EdgeType.RequiresQuest => Theme.QuestAvailable,
            EdgeType.CompletedBy => Theme.Accent,
            EdgeType.AssignedBy => Theme.Accent,
            _ => Theme.TextPrimary,
        };
    }

    // ── NAV button ──────────────────────────────────────────────────────

    private void DrawNavButton(ViewNode node)
    {
        // Only show NAV for nodes with world positions or quest nodes
        if (!IsNavigable(node.Node))
            return;

        ImGui.SameLine();
        bool isSelected = _navSet.Contains(node.NodeKey);
        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton($"NAV###{node.NodeKey}"))
        {
            // Shift+click = toggle, regular click = override
            if (ImGui.GetIO().KeyShift)
                _navSet.Toggle(node.NodeKey);
            else
                _navSet.Override(node.NodeKey);
        }

        if (isSelected)
            ImGui.PopStyleColor();
    }

    private static bool IsNavigable(Node node)
    {
        // Nodes with coordinates are directly navigable
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            return true;

        // Quests and items resolve via their frontier/sources
        return node.Type == NodeType.Quest || node.Type == NodeType.Item;
    }

    // ── Quest badge ─────────────────────────────────────────────────────

    private void DrawQuestBadge(string questKey)
    {
        var nodeState = _state.GetState(questKey);
        string badge;
        uint color;

        switch (nodeState)
        {
            case QuestCompleted:
                badge = "COMPLETED";
                color = Theme.QuestCompleted;
                break;
            case QuestActive:
                badge = "ACTIVE";
                color = Theme.QuestActive;
                break;
            case QuestImplicitlyActive:
                badge = "AVAILABLE (implicit)";
                color = Theme.QuestImplicit;
                break;
            default:
                badge = "NOT STARTED";
                color = Theme.TextSecondary;
                break;
        }

        ImGui.SameLine();
        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.Text($"  [{badge}]");
        ImGui.PopStyleColor();
    }
}
