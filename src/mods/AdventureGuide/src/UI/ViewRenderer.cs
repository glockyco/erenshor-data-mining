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
    private readonly QuestStateTracker _tracker;
    private readonly TrackerState _trackerState;

    public ViewRenderer(EntityGraph graph, GameState state, NavigationSet navSet,
        QuestStateTracker tracker, TrackerState trackerState)
    {
        _graph = graph;
        _state = state;
        _navSet = navSet;
        _tracker = tracker;
        _trackerState = trackerState;
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

        DrawHeader(root);

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();

        // Children: the dependency tree
        foreach (var child in root.Children)
            DrawNode(child, 0);
    }

    // ── Header ──────────────────────────────────────────────────────────

    private void DrawHeader(ViewNode root)
    {
        var quest = root.Node;
        string? dbName = quest.DbName;

        // Quest name + badge
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();
        DrawQuestBadge(root.NodeKey);

        // Track/Untrack button (only for non-completed quests with a DB name)
        if (dbName != null && !_tracker.IsCompleted(dbName))
        {
            ImGui.SameLine();
            bool tracked = _trackerState.IsTracked(dbName);
            if (tracked)
                ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);
            if (ImGui.SmallButton(tracked ? "Untrack" : "Track"))
            {
                if (tracked) _trackerState.Untrack(dbName);
                else _trackerState.Track(dbName);
            }
            if (tracked)
                ImGui.PopStyleColor();
        }

        // Level · Zone · Repeatable metadata line
        DrawMetadataLine(quest);

        // Acquisition sources: who gives this quest
        DrawAcquisitionSources(quest);

        // Turn-in targets: who completes this quest
        DrawCompletionTargets(quest);

        // Description
        if (!string.IsNullOrEmpty(quest.Description))
        {
            ImGui.Spacing();
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped(quest.Description);
            ImGui.PopStyleColor();
        }
    }

    private static void DrawMetadataLine(Node quest)
    {
        string meta = "";
        if (quest.Level.HasValue)
            meta = $"Lv {quest.Level.Value}";
        if (quest.Zone != null)
        {
            if (meta.Length > 0) meta += "  \u00b7  ";
            meta += quest.Zone;
        }
        if (quest.Repeatable)
        {
            if (meta.Length > 0) meta += "  \u00b7  ";
            meta += "Repeatable";
        }
        if (quest.Implicit)
        {
            if (meta.Length > 0) meta += "  \u00b7  ";
            meta += "Implicit";
        }

        if (meta.Length == 0)
            return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.Text(meta);
        ImGui.PopStyleColor();
    }

    private void DrawAcquisitionSources(Node quest)
    {
        var edges = _graph.OutEdges(quest.Key, EdgeType.AssignedBy);
        if (edges.Count == 0) return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        foreach (var edge in edges)
        {
            var target = _graph.GetNode(edge.Target);
            if (target == null) continue;

            string label = target.Type switch
            {
                NodeType.Character => FormatKeyword("Given by: ", target.DisplayName, edge.Keyword),
                NodeType.Item => $"Read: {target.DisplayName}",
                NodeType.Zone => $"Enter: {target.DisplayName}",
                NodeType.Quest => $"Chain from: {target.DisplayName}",
                _ => $"From: {target.DisplayName}",
            };

            // Append zone for character sources
            if (target.Type == NodeType.Character && target.Zone != null)
                label += $" ({target.Zone})";

            DrawNavButtonByKey(target);
            ImGui.SameLine();
            ImGui.Text(label);
        }
        ImGui.PopStyleColor();
    }

    private void DrawCompletionTargets(Node quest)
    {
        var edges = _graph.OutEdges(quest.Key, EdgeType.CompletedBy);
        if (edges.Count == 0) return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        foreach (var edge in edges)
        {
            var target = _graph.GetNode(edge.Target);
            if (target == null) continue;

            string label = target.Type switch
            {
                NodeType.Character => FormatKeyword("Turn in to: ", target.DisplayName, edge.Keyword),
                NodeType.Zone => $"Complete at: {target.DisplayName}",
                NodeType.Item => $"Complete by reading: {target.DisplayName}",
                _ => $"Complete: {target.DisplayName}",
            };

            if (target.Type == NodeType.Character && target.Zone != null)
                label += $" ({target.Zone})";

            DrawNavButtonByKey(target);
            ImGui.SameLine();
            ImGui.Text(label);
        }
        ImGui.PopStyleColor();
    }

    // ── Recursive node renderer ─────────────────────────────────────────

    private void DrawNode(ViewNode node, int depth)
    {
        if (node.IsCycleRef)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped($"  \u21bb {node.Node.DisplayName} (see above)");
            ImGui.PopStyleColor();
            return;
        }

        // Build the label from edge type + node data
        string label = FormatLabel(node);
        uint color = GetNodeColor(node);
        bool hasChildren = node.Children.Count > 0;

        // State indicator (checkmark for satisfied nodes)
        var nodeState = _state.GetState(node.NodeKey);
        string statePrefix = nodeState.IsSatisfied ? "\u2713 " : "";

        // NAV button on the left, before the label
        bool navigable = IsNavigable(node.Node);

        if (hasChildren)
        {
            if (navigable)
            {
                DrawNavButton(node);
                ImGui.SameLine();
            }
            ImGui.PushStyleColor(ImGuiCol.Text, color);
            bool open = ImGui.TreeNodeEx(
                $"{statePrefix}{label}###{node.NodeKey}_{depth}",
                node.DefaultExpanded ? ImGuiTreeNodeFlags.DefaultOpen : ImGuiTreeNodeFlags.None);
            ImGui.PopStyleColor();

            if (open)
            {
                foreach (var child in node.Children)
                    DrawNode(child, depth + 1);
                ImGui.TreePop();
            }
        }
        else
        {
            if (navigable)
            {
                DrawNavButton(node);
                ImGui.SameLine();
            }
            ImGui.PushStyleColor(ImGuiCol.Text, color);
            ImGui.BulletText($"{statePrefix}{label}");
            ImGui.PopStyleColor();
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
            return $"{prefix}{name} (\u00d7{quantity.Value})";
        return $"{prefix}{name}";
    }

    private static string FormatKeyword(string prefix, string name, string? keyword)
    {
        if (!string.IsNullOrEmpty(keyword))
            return $"{prefix}{name} \u2014 say \"{keyword}\"";
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

    // ── NAV buttons ─────────────────────────────────────────────────────

    /// <summary>NAV button for a dependency tree node.</summary>
    private void DrawNavButton(ViewNode node)
    {
        DrawNavButtonByKey(node.Node, node.NodeKey);
    }

    /// <summary>NAV button for a graph node (used in header for giver/turn-in).</summary>
    private void DrawNavButtonByKey(Node node, string? keyOverride = null)
    {
        if (!IsNavigable(node))
            return;

        string key = keyOverride ?? node.Key;
        bool isSelected = _navSet.Contains(key);
        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton($"NAV###{key}"))
        {
            if (ImGui.GetIO().KeyShift)
                _navSet.Toggle(key);
            else
                _navSet.Override(key);
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
