using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Plan.Semantics;
using AdventureGuide.State;
using AdventureGuide.UI.Tree;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders quest detail pages from canonical quest plans through a lazy tree
/// session. The player-facing tree only materializes one level at a time and
/// never renders cycle placeholders.
/// </summary>
public sealed class ViewRenderer
{
    private readonly EntityGraph _graph;
    private readonly GameState _state;
    private readonly NavigationSet _navSet;
    private readonly QuestStateTracker _tracker;
    private readonly TrackerState _trackerState;

    private QuestPlan? _currentPlan;
    private QuestTreeSession? _currentSession;
    private LazyTreeProjector? _currentProjector;

    public ViewRenderer(EntityGraph graph, GameState state, NavigationSet navSet,
        QuestStateTracker tracker, TrackerState trackerState)
    {
        _graph = graph;
        _state = state;
        _navSet = navSet;
        _tracker = tracker;
        _trackerState = trackerState;
    }

    /// <summary>Render a full quest detail page from a canonical quest plan.</summary>
    public void Draw(QuestPlanProjection? projection)
    {
        if (projection == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("Select a quest from the list.");
            ImGui.PopStyleColor();
            return;
        }

        EnsureSession(projection.Plan);
        var root = _currentPlan?.GetNode(_currentPlan.RootId) as PlanEntityNode;
        if (root == null)
        {
            DrawNotice("No guide data available for this quest.");
            return;
        }

        DrawHeader(root);

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();

        var rootChildren = _currentProjector!.GetRootChildren();
        if (rootChildren.Count == 0)
        {
            DrawNotice("No guide data available for this quest.");
        }
        else if (ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
        {
            var questState = _state.GetState(root.NodeKey);
            ImGui.Indent(Theme.IndentWidth);
            for (int i = 0; i < rootChildren.Count; i++)
            {
                ImGui.PushID(i);
                DrawTreeRef(rootChildren[i], questState);
                ImGui.PopID();
            }
            ImGui.Unindent(Theme.IndentWidth);

            if (_graph.OutEdges(root.NodeKey, EdgeType.CompletedBy).Count == 0)
                DrawNotice("Completion method not in guide data — may be scripted.");
        }

        ImGui.Spacing();
        DrawRewards(root.Node);
    }

    private void EnsureSession(QuestPlan plan)
    {
        if (ReferenceEquals(_currentPlan, plan) && _currentSession != null && _currentProjector != null)
            return;

        _currentPlan = plan;
        _currentSession = new QuestTreeSession(plan);
        _currentProjector = new LazyTreeProjector(plan, _currentSession);
    }

    // ── Header ──────────────────────────────────────────────────────────

    private void DrawHeader(PlanEntityNode root)
    {
        var quest = root.Node;
        string? dbName = quest.DbName;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();
        DrawQuestBadge(root.NodeKey);

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

        DrawMetadataLine(quest);

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
            if (meta.Length > 0) meta += "  ·  ";
            meta += quest.Zone;
        }
        if (quest.Repeatable)
        {
            if (meta.Length > 0) meta += "  ·  ";
            meta += "Repeatable";
        }

        if (meta.Length == 0)
            return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.Text(meta);
        ImGui.PopStyleColor();
    }

    // ── Lazy tree renderer ──────────────────────────────────────────────

    private void DrawTreeRef(TreeRef treeRef, NodeState questState, string? labelPrefix = null)
    {
        var node = _currentPlan!.GetNode(treeRef.NodeId);
        if (node == null)
            return;

        if (node is PlanGroupNode group)
        {
            DrawGroupRef(treeRef, group, questState);
            return;
        }

        var entity = (PlanEntityNode)node;
        if (entity.Node.Type == NodeType.Quest)
            questState = _state.GetState(entity.NodeKey);

        string label = FormatLabel(entity, treeRef.IncomingLink);
        if (!string.IsNullOrEmpty(labelPrefix))
            label = labelPrefix + label;

        uint color = GetNodeColor(entity, treeRef.IncomingLink);
        var unlockChildren = _currentProjector!.GetUnlockChildren(treeRef);
        var childRefs = _currentProjector.GetChildren(treeRef);
        bool hasTreeContent = unlockChildren.Count > 0 || childRefs.Count > 0;
        bool navigable = IsNavigable(entity.Node);

        if (hasTreeContent)
        {
            if (navigable)
            {
                DrawNavButtonByKey(entity.Node, entity.NodeKey);
                ImGui.SameLine();
            }

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            bool open = ImGui.TreeNodeEx($"{label}###{treeRef.Id}");
            ImGui.PopStyleColor();
            _currentSession!.SetExpanded(treeRef.Id, open);

            if (open)
            {
                if (unlockChildren.Count == 1)
                {
                    var unlockNode = _currentPlan.GetNode(unlockChildren[0].NodeId) as PlanEntityNode;
                    string prefix = unlockNode?.Node.Type == NodeType.Door ? "Unlock: " : "Requires: ";
                    DrawTreeRef(unlockChildren[0], questState, prefix);
                }
                else if (unlockChildren.Count > 1)
                {
                    ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                    ImGui.TextUnformatted("Requires all of:");
                    ImGui.PopStyleColor();
                    ImGui.Indent(Theme.IndentWidth);
                    for (int i = 0; i < unlockChildren.Count; i++)
                    {
                        ImGui.PushID($"unlock_{i}");
                        DrawTreeRef(unlockChildren[i], questState);
                        ImGui.PopID();
                    }
                    ImGui.Unindent(Theme.IndentWidth);
                }

                for (int i = 0; i < childRefs.Count; i++)
                {
                    ImGui.PushID($"child_{i}");
                    DrawTreeRef(childRefs[i], questState);
                    ImGui.PopID();
                }

                ImGui.TreePop();
            }
        }
        else
        {
            if (navigable)
            {
                DrawNavButtonByKey(entity.Node, entity.NodeKey);
                ImGui.SameLine();
            }

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            ImGui.BulletText(label);
            ImGui.PopStyleColor();
        }
    }

    private void DrawGroupRef(TreeRef treeRef, PlanGroupNode group, NodeState questState)
    {
        string label = group.Label ?? (group.GroupKind == PlanGroupKind.AnyOf ? "One of" : "Requires all of");
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        bool open = ImGui.TreeNodeEx($"{label}###{treeRef.Id}", ImGuiTreeNodeFlags.DefaultOpen);
        ImGui.PopStyleColor();
        _currentSession!.SetExpanded(treeRef.Id, open);
        if (!open)
            return;

        var children = _currentProjector!.GetChildren(treeRef);
        for (int i = 0; i < children.Count; i++)
        {
            ImGui.PushID($"group_{i}");
            DrawTreeRef(children[i], questState);
            ImGui.PopID();
        }
        ImGui.TreePop();
    }

    private static void DrawNotice(string text)
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextWrapped(text);
        ImGui.PopStyleColor();
    }

    // ── Label formatting ────────────────────────────────────────────────

    private string FormatLabel(PlanEntityNode node, PlanLink? link)
    {
        var edgeType = link?.EdgeType;
        var n = node.Node;
        string name = n.DisplayName;

        if (edgeType == null)
            return name;

        string prefix = edgeType.Value switch
        {
            EdgeType.RequiresQuest => $"Requires: {name}",
            EdgeType.RequiresItem => FormatHaveNeed("Collect: ", name, node, link),
            EdgeType.StepTalk => FormatKeyword("Talk to ", name, link?.Keyword),
            EdgeType.StepKill => $"Kill: {name}",
            EdgeType.StepTravel => $"Travel to: {name}",
            EdgeType.StepShout => !string.IsNullOrEmpty(link?.Keyword)
                ? $"Shout '{link!.Keyword}' near {name}"
                : $"Shout near {name}",
            EdgeType.StepRead => $"Read: {name}",
            EdgeType.CompletedBy => FormatKeyword("Turn in to ", name, link?.Keyword),
            EdgeType.AssignedBy => FormatAssignment(node, link),
            EdgeType.CraftedFrom => $"Crafted via: {name}",
            EdgeType.RequiresMaterial => FormatHaveNeed("Ingredient: ", name, node, link),
            EdgeType.DropsItem => FormatChance($"Drops from: {name}", link?.Note == null ? null : ParseChance(link.Note)),
            EdgeType.SellsItem => $"Vendor: {name}",
            EdgeType.GivesItem => FormatKeyword("Talk to ", name, link?.Keyword),
            EdgeType.YieldsItem => n.Type switch
            {
                NodeType.MiningNode => $"Mine: {name}",
                NodeType.Water      => $"Fish at: {name}",
                _                   => $"Collect: {name}",
            },
            EdgeType.RewardsItem => $"Quest reward: {name}",
            _ => $"[{edgeType.Value}] {name}",
        };

        prefix += FormatNodeMetadata(node, link);
        return prefix;
    }

    private string FormatHaveNeed(string prefix, string name, PlanEntityNode node, PlanLink? link)
    {
        int need = link?.Quantity ?? 1;
        if (need <= 1)
            return $"{prefix}{name}";

        int have = _tracker.CountItem(node.NodeKey);
        return $"{prefix}{name} ({have}/{need})";
    }

    private static string FormatKeyword(string prefix, string name, string? keyword)
        => !string.IsNullOrEmpty(keyword) ? $"{prefix}{name} — say \"{keyword}\"" : $"{prefix}{name}";

    private static string FormatChance(string text, float? chance)
        => chance.HasValue && chance.Value < 1.0f ? $"{text} ({chance.Value:P0})" : text;

    private static float? ParseChance(string? note) => null;

    private static string FormatNodeMetadata(PlanEntityNode node, PlanLink? link)
    {
        var parts = new List<string>(3);
        bool showLevel = link?.EdgeType is EdgeType.StepKill or EdgeType.DropsItem or EdgeType.YieldsItem or EdgeType.StepTravel;

        if (showLevel)
        {
            int? level = node.EffectiveLevel ?? node.Node.Level;
            if (level.HasValue)
                parts.Add($"Lv {level.Value}");
        }

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

        if (parts.Count == 0)
            return string.Empty;

        return " (" + string.Join(", ", parts) + ")";
    }

    private static string FormatAssignment(PlanEntityNode node, PlanLink? link)
    {
        string name = node.Node.DisplayName;
        return node.Node.Type switch
        {
            NodeType.Item => $"Read: {name}",
            NodeType.Zone => $"Enter: {name}",
            NodeType.Quest => $"Complete: {name}",
            _ => FormatKeyword("Talk to ", name, link?.Keyword),
        };
    }

    // ── Colors ──────────────────────────────────────────────────────────

    private uint GetNodeColor(PlanEntityNode node, PlanLink? link)
    {
        if (node.Status == PlanStatus.Satisfied)
            return Theme.QuestCompleted;
        if (_navSet.Contains(node.NodeKey))
            return Theme.NavManualOverride;
        if (link?.Semantic.Phase == DependencyPhase.Source)
            return Theme.SourceDimmed;
        return Theme.TextPrimary;
    }

    // ── NAV buttons ─────────────────────────────────────────────────────

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

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            if (!isSelected)
                ImGui.TextUnformatted("Click to navigate\nShift+click to add");
            else if (_navSet.Count == 1)
                ImGui.TextUnformatted("Click to stop navigating\nShift+click to remove");
            else
                ImGui.TextUnformatted("Click to navigate here only\nShift+click to remove");
            ImGui.EndTooltip();
        }
    }

    private static bool IsNavigable(Node node)
    {
        if (node.X.HasValue && node.Y.HasValue && node.Z.HasValue)
            return true;

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
                badge = "[COMPLETED]";
                color = Theme.QuestCompleted;
                break;
            case QuestActive:
            case QuestImplicitlyActive:
                badge = "[ACTIVE]";
                color = Theme.Accent;
                break;
            default:
                badge = "[NOT STARTED]";
                color = Theme.TextSecondary;
                break;
        }

        ImGui.SameLine();
        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.TextUnformatted(badge);
        ImGui.PopStyleColor();
    }

    // ── Rewards section ─────────────────────────────────────────────────

    private void DrawRewards(Node quest)
    {
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

        if (quest.XpReward is > 0)
            ImGui.Text($"{quest.XpReward} XP");
        if (quest.GoldReward is > 0)
            ImGui.Text($"{quest.GoldReward} Gold");

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
        if (rewardEdges.Count == 0 && quest.RewardItemKey != null)
        {
            var itemNode = _graph.GetNode(quest.RewardItemKey);
            ImGui.Text(itemNode?.DisplayName ?? quest.RewardItemKey);
        }

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

        for (int i = 0; i < charEdges.Count; i++)
        {
            var charNode = _graph.GetNode(charEdges[i].Target);
            if (charNode == null) continue;
            string text = charNode.Zone != null
                ? $"Enables {charNode.DisplayName} in {charNode.Zone}"
                : $"Enables {charNode.DisplayName}";
            ImGui.Text(text);
        }

        for (int i = 0; i < vendorEdges.Count; i++)
        {
            var edge = vendorEdges[i];
            var itemNode = _graph.GetNode(edge.Target);
            if (itemNode == null) continue;
            string vendorName = "vendor";
            if (edge.Note != null)
            {
                var vendorNode = _graph.GetNode(edge.Note);
                if (vendorNode != null)
                    vendorName = vendorNode.DisplayName;
            }
            ImGui.Text($"Unlocks {itemNode.DisplayName} at {vendorName}");
        }

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
}
