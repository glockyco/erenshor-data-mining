using AdventureGuide.Resolution;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Views;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders quest detail pages: header, dependency tree, and rewards section.
///
/// The dependency tree is the primary content — steps, required items, prerequisites,
/// acquisition sources, and turn-in targets rendered recursively from ViewNode trees.
/// The rewards section follows, showing what the player gets for completing the quest.
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

    /// <summary>Render a full quest detail page from a shared quest resolution.</summary>
    public void Draw(QuestResolution? resolution)
    {
        if (resolution?.ViewRoot is not EntityViewNode root)
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

        if (root.Children.Count == 0)
        {
            DrawNotice("No guide data available for this quest.");
        }
        else if (ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
        {
            var questState = _state.GetState(root.NodeKey);
            ImGui.Indent(Theme.IndentWidth);
            // Detect runs of consecutive VariantGroupNodes. A "One of:" header
            // and indent wraps each run; the separator was replaced by this
            // structure so no special characters are needed.
            bool inVariantRun = false;
            for (int i = 0; i < root.Children.Count; i++)
            {
                var child = root.Children[i];
                bool isVariant = child is VariantGroupNode;

                if (isVariant && !inVariantRun)
                {
                    DrawOneOfHeader();
                    ImGui.Indent(Theme.IndentWidth);
                    inVariantRun = true;
                }
                else if (!isVariant && inVariantRun)
                {
                    ImGui.Unindent(Theme.IndentWidth);
                    inVariantRun = false;
                }

                DrawNode(child, 0, questState);
            }

            if (inVariantRun)
                ImGui.Unindent(Theme.IndentWidth);
            ImGui.Unindent(Theme.IndentWidth);

            if (_graph.OutEdges(root.NodeKey, EdgeType.CompletedBy).Count == 0)
                DrawNotice("Completion method not in guide data — may be scripted.");
        }

        ImGui.Spacing();
        DrawRewards(root.Node);
    }

    // ── Header ──────────────────────────────────────────────────────────

    private void DrawHeader(EntityViewNode root)
    {
        var quest = root.Node;
        string? dbName = quest.DbName;

        // Quest name + badge
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();
        DrawQuestBadge(root.NodeKey);

        // Quest-level navigation and tracking controls.

        ImGui.SameLine();
        DrawNavButtonByKey(quest, root.NodeKey);

        if (dbName != null)
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

        if (meta.Length == 0)
            return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.Text(meta);
        ImGui.PopStyleColor();
    }

    // ── Recursive node renderer ─────────────────────────────────────────

    /// <summary>Render a single dependency tree node with children.</summary>
    private void DrawNode(ViewNode node, int depth, NodeState questState)
    {
        if (node is VariantGroupNode vgContainer)
        {
            DrawVariantContainer(vgContainer, depth, questState);
            return;
        }

        var entityNode = (EntityViewNode)node;

        if (entityNode.IsCycleRef)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped($"  {entityNode.Node.DisplayName} (see above)");
            ImGui.PopStyleColor();
            return;
        }

        // When entering a sub-quest node, switch to that quest's state.
        if (entityNode.Node.Type == Graph.NodeType.Quest)
            questState = _state.GetState(entityNode.NodeKey);

        // Single source of truth: classify the edge once, derive all visuals from it.
        var role = FrontierComputer.ClassifyEdge(entityNode, _state, questState);
        string label = FormatLabel(entityNode);
        uint color = GetNodeColor(entityNode, role);
        bool hasChildren = entityNode.Children.Count > 0;
        // Color already communicates state; no prefix glyph needed.


        // NAV button on the left, before the label
        bool navigable = IsNavigable(entityNode.Node);

        if (hasChildren)
        {
            if (navigable)
            {
                DrawNavButton(entityNode);
                ImGui.SameLine();
            }
            ImGui.PushStyleColor(ImGuiCol.Text, color);
            bool open = ImGui.TreeNodeEx(
                $"{label}###{entityNode.NodeKey}_{depth}",
                entityNode.DefaultExpanded ? ImGuiTreeNodeFlags.DefaultOpen : ImGuiTreeNodeFlags.None);
            ImGui.PopStyleColor();


            if (open)
            {
                foreach (var child in entityNode.Children)
                    DrawNode(child, depth + 1, questState);
                ImGui.TreePop();
            }
        }
        else
        {
            if (navigable)
            {
                DrawNavButton(entityNode);
                ImGui.SameLine();
            }
            ImGui.PushStyleColor(ImGuiCol.Text, color);
            ImGui.BulletText(label);
            ImGui.PopStyleColor();
        }

        // Inline unlock dependency sub-tree when this node is blocked
        if (entityNode.UnlockDependency is EntityViewNode unlockNode)
        {
            ImGui.Indent(Theme.IndentWidth);
            var unlockState = _state.GetState(unlockNode.NodeKey);
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            if (ImGui.TreeNodeEx($"Requires: {unlockNode.Node.DisplayName}###{entityNode.NodeKey}_{unlockNode.NodeKey}_{depth}",
                    ImGuiTreeNodeFlags.DefaultOpen))
            {
                ImGui.PopStyleColor();
                foreach (var child in unlockNode.Children)
                    DrawNode(child, depth + 1, unlockState);
                ImGui.TreePop();
            }
            else
            {
                ImGui.PopStyleColor();
            }
            ImGui.Unindent(Theme.IndentWidth);
        }
    }


    private static void DrawNotice(string text)
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextWrapped(text);
        ImGui.PopStyleColor();
    }


    // ── OR-variant container renderer ────────────────────────────────────

    /// <summary>
    /// Render an OR-variant group container. Labelled containers (where the
    /// variant's reward item differs from siblings) get a collapsible section
    /// header. Unlabelled containers render their items inline at the same
    /// depth — the "\u2500 or \u2500" separator inserted by the Objectives loop
    /// communicates the OR relationship without extra nesting.
    /// </summary>
    private void DrawVariantContainer(VariantGroupNode container, int depth, NodeState questState)
    {
        if (container.HasLabel)
        {
            // Labelled group: "Malaroth Feed:" header then indented items.
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextUnformatted($"{container.Label}:");
            ImGui.PopStyleColor();
            ImGui.Indent(Theme.IndentWidth);
            foreach (var child in container.Children)
                DrawNode(child, depth + 1, questState);
            ImGui.Unindent(Theme.IndentWidth);
        }
        else
        {
            // Unlabelled: items flat — the "One of:" header from the Objectives
            // loop already provides context and visual indentation.
            foreach (var child in container.Children)
                DrawNode(child, depth, questState);
        }
    }

    /// <summary>
    /// "One of:" header rendered before the first VariantGroupNode in a run.
    /// Uses only ASCII text to avoid font-rendering issues.
    /// </summary>
    private static void DrawOneOfHeader()
    {
        ImGui.Spacing();
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextUnformatted("One of:");
        ImGui.PopStyleColor();
    }


    // ── Rewards section ─────────────────────────────────────────────────

    /// <summary>
    /// Collapsible rewards section showing XP, gold, items, zone/NPC unlocks,
    /// quest chain, faction effects, and also-completes. Reads from Node fields
    /// and outgoing graph edges.
    /// </summary>
    private void DrawRewards(Node quest)
    {
        // Check if there's anything to show before rendering the header
        bool hasNodeRewards = quest.XpReward is > 0
            || quest.GoldReward is > 0
            || quest.RewardItemKey != null;

        var rewardEdges = _graph.OutEdges(quest.Key, EdgeType.RewardsItem);
        var chainEdges = _graph.OutEdges(quest.Key, EdgeType.ChainsTo);
        var alsoEdges = _graph.OutEdges(quest.Key, EdgeType.AlsoCompletes);
        var zoneLineEdges = _graph.OutEdges(quest.Key, EdgeType.UnlocksZoneLine);
        var charEdges = _graph.OutEdges(quest.Key, EdgeType.UnlocksCharacter);
        var factionEdges = _graph.OutEdges(quest.Key, EdgeType.AffectsFaction);
        var vendorEdges = _graph.OutEdges(quest.Key, EdgeType.UnlocksVendorItem);

        bool hasEdgeRewards = rewardEdges.Count > 0
            || chainEdges.Count > 0
            || alsoEdges.Count > 0
            || zoneLineEdges.Count > 0
            || charEdges.Count > 0
            || factionEdges.Count > 0
            || vendorEdges.Count > 0;

        if (!hasNodeRewards && !hasEdgeRewards)
            return;

        if (!ImGui.CollapsingHeader("Rewards", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        // XP and Gold
        if (quest.XpReward is > 0)
            ImGui.Text($"{quest.XpReward} XP");
        if (quest.GoldReward is > 0)
            ImGui.Text($"{quest.GoldReward} Gold");

        // Reward items (from edges — more reliable than RewardItemKey since
        // the edge target gives us the display name)
        // Reward items. When edges carry group fields and rewards differ across
        // variants, each item is listed separately (no merging). When all
        // variants give the same item (or edges are ungrouped), deduplication
        // prevents the same item appearing multiple times.
        if (rewardEdges.Count > 0)
        {
            bool variantGrouped = rewardEdges.Any(e => e.Group != null)
                && rewardEdges.Select(e => e.Group).Distinct().Count() > 1;
            if (variantGrouped)
            {
                foreach (var edge in rewardEdges)
                {
                    var itemNode = _graph.GetNode(edge.Target);
                    if (itemNode != null) ImGui.Text(itemNode.DisplayName);
                }
            }
            else
            {
                var shown = new HashSet<string>(StringComparer.Ordinal);
                for (int i = 0; i < rewardEdges.Count; i++)
                {
                    if (!shown.Add(rewardEdges[i].Target)) continue;
                    var itemNode = _graph.GetNode(rewardEdges[i].Target);
                    if (itemNode != null) ImGui.Text(itemNode.DisplayName);
                }
            }
        }
        // Fallback: if no RewardsItem edges but Node has a reward key
        if (rewardEdges.Count == 0 && quest.RewardItemKey != null)
        {
            var itemNode = _graph.GetNode(quest.RewardItemKey);
            ImGui.Text(itemNode?.DisplayName ?? quest.RewardItemKey);
        }

        // Zone line unlocks
        for (int i = 0; i < zoneLineEdges.Count; i++)
        {
            var zlNode = _graph.GetNode(zoneLineEdges[i].Target);
            if (zlNode == null) continue;
            string dest = zlNode.DestinationDisplay ?? zlNode.DisplayName;
            string from = zlNode.Zone ?? zlNode.Scene ?? "";
            if (from.Length > 0)
                ImGui.Text($"Opens path: {from} > {dest}");
            else
                ImGui.Text($"Opens path to {dest}");
        }

        // Character unlocks
        for (int i = 0; i < charEdges.Count; i++)
        {
            var charNode = _graph.GetNode(charEdges[i].Target);
            if (charNode == null) continue;
            string text = charNode.Zone != null
                ? $"Enables {charNode.DisplayName} in {charNode.Zone}"
                : $"Enables {charNode.DisplayName}";
            ImGui.Text(text);
        }

        // Vendor item unlocks
        for (int i = 0; i < vendorEdges.Count; i++)
        {
            var edge = vendorEdges[i];
            var itemNode = _graph.GetNode(edge.Target);
            if (itemNode == null) continue;
            // Vendor character key is stored in Edge.Note
            string vendorName = "vendor";
            if (edge.Note != null)
            {
                var vendorNode = _graph.GetNode(edge.Note);
                if (vendorNode != null)
                    vendorName = vendorNode.DisplayName;
            }
            ImGui.Text($"Unlocks {itemNode.DisplayName} at {vendorName}");
        }

        // Quest chain
        for (int i = 0; i < chainEdges.Count; i++)
        {
            var nextQuest = _graph.GetNode(chainEdges[i].Target);
            if (nextQuest == null) continue;
            if (ImGui.Selectable($"Chains to: {nextQuest.DisplayName}###chain_{nextQuest.Key}"))
            {
                if (nextQuest.DbName != null)
                    _tracker.SelectQuest(nextQuest.DbName);
            }
        }

        // Also completes
        for (int i = 0; i < alsoEdges.Count; i++)
        {
            var otherQuest = _graph.GetNode(alsoEdges[i].Target);
            if (otherQuest == null) continue;
            if (ImGui.Selectable($"Also completes: {otherQuest.DisplayName}###also_{otherQuest.Key}"))
            {
                if (otherQuest.DbName != null)
                    _tracker.SelectQuest(otherQuest.DbName);
            }
        }

        // Faction effects
        for (int i = 0; i < factionEdges.Count; i++)
        {
            var edge = factionEdges[i];
            var factionNode = _graph.GetNode(edge.Target);
            if (factionNode == null) continue;
            int amount = edge.Amount ?? 0;
            string sign = amount >= 0 ? "+" : "";
            ImGui.Text($"{factionNode.DisplayName}: {sign}{amount}");
        }

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);
    }

    // ── Label formatting ────────────────────────────────────────────────

    private string FormatLabel(EntityViewNode node)
    {
        var edge = node.Edge;
        var n = node.Node;
        string name = n.DisplayName;

        if (node.EdgeType == null)
            return name;

        string prefix = node.EdgeType.Value switch
        {
            EdgeType.RequiresQuest => "Requires: ",
            EdgeType.RequiresItem => FormatHaveNeed("Obtain: ", name, edge),
            EdgeType.StepTalk => FormatKeyword("Talk to ", name, edge?.Keyword),
            EdgeType.StepKill => $"Kill: {name}",
            EdgeType.StepTravel => $"Travel to: {name}",
            EdgeType.StepShout => FormatKeyword("Shout at ", name, edge?.Keyword),
            EdgeType.StepRead => $"Read: {name}",
            EdgeType.CompletedBy => FormatKeyword("Turn in to ", name, edge?.Keyword),
            EdgeType.AssignedBy => FormatAssignment(node),
            EdgeType.CraftedFrom => $"Crafted via: {name}",
            EdgeType.RequiresMaterial => FormatHaveNeed("Ingredient: ", name, edge),
            EdgeType.DropsItem => FormatChance($"Drops from: {name}", edge?.Chance),
            EdgeType.SellsItem => $"Vendor: {name}",
            EdgeType.GivesItem => FormatKeyword("Talk to ", name, edge?.Keyword),
            EdgeType.YieldsItem => $"Gathered from: {name}",
            EdgeType.RewardsItem => $"Quest reward: {name}",
            _ => $"[{node.EdgeType.Value}] {name}",
        };

        // Append metadata: level and zone(s) for source nodes,
        // or just zone for other nodes.
        prefix += FormatNodeMetadata(node);

        return prefix;
    }

    /// <summary>
    /// Format item requirement with have/need counts when quantity > 1.
    /// Shows "Obtain: Iron Ore (2/3)" instead of "Obtain: Iron Ore (×3)".
    /// </summary>
    private string FormatHaveNeed(string prefix, string name, Edge? edge)
    {
        int need = edge?.Quantity ?? 1;
        if (need <= 1)
            return $"{prefix}{name}";

        string itemKey = edge!.Target;
        int have = _tracker.CountItem(itemKey);
        return $"{prefix}{name} ({have}/{need})";
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

    /// <summary>
    /// Build a parenthesized metadata suffix for a tree node label.
    /// Level is shown only for combat-relevant edges (kill targets, drop
    /// sources) — not for friendly NPCs (quest givers, turn-in, vendors,
    /// talk targets). Uses EffectiveLevel (max of character level and zone
    /// median) when available, falling back to the node's raw level.
    /// </summary>
    private static string FormatNodeMetadata(EntityViewNode node)
    {
        var parts = new List<string>(3);

        // Level: only for edges where combat difficulty matters
        bool showLevel = node.EdgeType is EdgeType.StepKill
            or EdgeType.DropsItem
            or EdgeType.YieldsItem
            or EdgeType.StepTravel;

        if (showLevel)
        {
            int? level = node.EffectiveLevel ?? node.Node.Level;
            if (level.HasValue)
                parts.Add($"Lv {level.Value}");
        }

        // Zones: always shown when available
        if (node.SourceZones != null && node.SourceZones.Count > 0)
        {
            if (node.SourceZones.Count <= 3)
                parts.Add(string.Join(", ", node.SourceZones));
            else
                parts.Add($"{node.SourceZones.Count} zones");
        }
        else if (node.Node.Zone != null)
        {
            parts.Add(node.Node.Zone);
        }

        // Time restriction: day/night-only fishables
        if (node.Edge?.TimeRestriction != null)
            parts.Add(node.Edge.TimeRestriction == "day" ? "day only" : "night only");

        if (parts.Count == 0)
            return "";

        return " (" + string.Join(", ", parts) + ")";
    }

    private static string FormatAssignment(EntityViewNode node)
    {
        string name = node.Node.DisplayName;
        var edge = node.Edge;
        return node.Node.Type switch
        {
            Graph.NodeType.Item => $"Read: {name}",
            Graph.NodeType.Zone => $"Enter: {name}",
            Graph.NodeType.Quest => $"Complete: {name}",
            _ => FormatKeyword("Talk to ", name, edge?.Keyword),
        };
    }

    // ── Colors ──────────────────────────────────────────────────────────

    private uint GetNodeColor(ViewNode node, FrontierComputer.EdgeRole role)
    {
        if (role == FrontierComputer.EdgeRole.Done)
            return Theme.QuestCompleted;

        if (_navSet.Contains(node.NodeKey))
            return Theme.NavManualOverride;

        return role switch
        {
            FrontierComputer.EdgeRole.Source => Theme.SourceDimmed,
            _ => Theme.TextPrimary,
        };
    }

    // ── NAV buttons ─────────────────────────────────────────────────────

    /// <summary>NAV button for a dependency tree node.</summary>
    private void DrawNavButton(EntityViewNode node)
    {
        if (!IsNavigable(node.Node))
            return;

        string key = node.NodeKey;
        bool isSelected = _navSet.Contains(key);
        if (isSelected)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton($"NAV###{key}"))
        {
            if (ImGui.GetIO().KeyShift)
                _navSet.Toggle(key, node);
            else if (isSelected && _navSet.Count == 1)
                _navSet.Clear();
            else
                _navSet.Override(key, node);
        }

        if (isSelected)
            ImGui.PopStyleColor();
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
            else if (isSelected && _navSet.Count == 1)
                _navSet.Clear();
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

        // Characters resolve via EntityRegistry or spawn point edges
        // Items resolve via drop/vendor/gather source positions
        // Quests resolve via their frontier
        // Zone lines, spawn points, mining nodes have static coords
        return node.Type switch
        {
            NodeType.Quest => true,
            NodeType.Item => true,
            NodeType.Character => true,
            NodeType.Zone => true,
            NodeType.ZoneLine => true,
            NodeType.SpawnPoint => true,
            NodeType.MiningNode => true,
            NodeType.Water => true,
            NodeType.Forge => true,
            NodeType.ItemBag => true,
            _ => false,
        };
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
