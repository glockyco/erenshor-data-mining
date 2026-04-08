using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.UI.Tree;
using ImGuiNET;

namespace AdventureGuide.UI;

public sealed class ViewRenderer
{
    private readonly EntityGraph _graph;
    private readonly GameState _state;
    private readonly NavigationSet _navSet;
    private readonly QuestStateTracker _tracker;
    private readonly TrackerState _trackerState;
    private readonly AdventureGuide.CompiledGuide.CompiledGuide _compiledGuide;
    private readonly SpecTreeProjector _specProjector;

    public ViewRenderer(
        EntityGraph graph,
        GameState state,
        AdventureGuide.CompiledGuide.CompiledGuide guide,
        NavigationSet navSet,
        QuestStateTracker tracker,
        TrackerState trackerState,
        SpecTreeProjector specProjector)
    {
        _graph = graph;
        _state = state;
        _compiledGuide = guide;
        _navSet = navSet;
        _tracker = tracker;
        _trackerState = trackerState;
        _specProjector = specProjector;
    }

    public void Draw(int? questIndex)
    {
        if (questIndex == null)
        {
            DrawNotice("Select a quest from the list.");
            return;
        }

        int questNodeId = _compiledGuide.QuestNodeId(questIndex.Value);
        string questKey = _compiledGuide.GetNodeKey(questNodeId);
        var quest = _graph.GetNode(questKey);
        if (quest == null)
        {
            DrawNotice("No guide data available for this quest.");
            return;
        }

        DrawHeader(quest, questKey);

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();

        var rootChildren = _specProjector.GetRootChildren(questIndex.Value);
        string? completionFallback = GetCompletionFallbackNotice(_graph, quest);
        if (rootChildren.Count == 0 && completionFallback == null)
        {
            DrawNotice("No guide data available for this quest.");
        }
        else if (ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
        {
            ImGui.Indent(Theme.IndentWidth);
            for (int i = 0; i < rootChildren.Count; i++)
            {
                ImGui.PushID($"spec_root_{i}");
                DrawSpecTreeRef(rootChildren[i]);
                ImGui.PopID();
            }

            if (completionFallback != null)
                DrawNoticeGroup("How to complete", completionFallback);

            ImGui.Unindent(Theme.IndentWidth);
        }

        ImGui.Spacing();
        DrawRewards(quest);
    }

    private void DrawSpecTreeRef(SpecTreeRef treeRef)
    {
        var node = ResolveGraphNode(treeRef.NodeId);
        bool navigable = node != null && IsNavigable(node);
        var unlockChildren = _specProjector.GetUnlockChildren(treeRef);
        var children = _specProjector.GetChildren(treeRef);
        bool hasTreeContent = unlockChildren.Count > 0 || children.Count > 0;
        uint color = GetNodeColor(treeRef, node);

        if (hasTreeContent)
        {
            if (navigable)
            {
                DrawNavButtonByKey(node!);
                ImGui.SameLine();
            }

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            bool open = ImGui.TreeNodeEx($"{treeRef.Label}###{treeRef.Kind}:{treeRef.NodeId}");
            ImGui.PopStyleColor();
            if (!open)
                return;

            for (int i = 0; i < unlockChildren.Count; i++)
            {
                ImGui.PushID($"unlock_{i}");
                DrawSpecTreeRef(unlockChildren[i]);
                ImGui.PopID();
            }

            for (int i = 0; i < children.Count; i++)
            {
                ImGui.PushID($"child_{i}");
                DrawSpecTreeRef(children[i]);
                ImGui.PopID();
            }

            ImGui.TreePop();
            return;
        }

        if (navigable)
        {
            DrawNavButtonByKey(node!);
            ImGui.SameLine();
        }

        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.BulletText(treeRef.Label);
        ImGui.PopStyleColor();
    }

    private Node? ResolveGraphNode(int nodeId)
    {
        string key = _compiledGuide.GetNodeKey(nodeId);
        return _graph.GetNode(key);
    }

    private void DrawHeader(Node quest, string questKey)
    {
        string? dbName = quest.DbName;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();
        DrawQuestBadge(questKey);

        ImGui.SameLine();
        DrawNavButtonByKey(quest, questKey);

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

    private static void DrawNotice(string text)
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextWrapped(text);
        ImGui.PopStyleColor();
    }

    private static void DrawNoticeGroup(string label, string text)
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        bool open = ImGui.TreeNodeEx(label, ImGuiTreeNodeFlags.DefaultOpen);
        ImGui.PopStyleColor();
        if (!open)
            return;

        DrawNotice(text);
        ImGui.TreePop();
    }

    internal static string? GetCompletionFallbackNotice(EntityGraph graph, Node quest) =>
        graph.OutEdges(quest.Key, EdgeType.CompletedBy).Count == 0
            ? "Completion method not in guide data. Quest may be scripted or not yet completable."
            : null;

    private uint GetNodeColor(SpecTreeRef treeRef, Node? node)
    {
        if (treeRef.IsCompleted)
            return Theme.QuestCompleted;

        if (node != null && _navSet.Contains(node.Key))
            return Theme.NavManualOverride;

        if (treeRef.IsBlocked)
            return Theme.SourceDimmed;

        return Theme.TextPrimary;
    }

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
                badge = "[ACTIVE]";
                color = Theme.Accent;
                break;
            case QuestImplicitlyAvailable:
                badge = "[COMPLETABLE]";
                color = Theme.QuestImplicit;
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

    private static string FormatKeyword(string prefix, string name, string? keyword) =>
        !string.IsNullOrEmpty(keyword) ? $"{prefix}{name} — say \"{keyword}\"" : $"{prefix}{name}";

    internal static string FormatCompletion(Node node, string? keyword)
    {
        string name = node.DisplayName;
        return node.Type switch
        {
            NodeType.Character => FormatKeyword("Turn in to ", name, keyword),
            NodeType.Item => $"Read: {name}",
            NodeType.Zone => $"Enter: {name}",
            NodeType.ZoneLine => $"Travel to: {name}",
            NodeType.Quest => $"Complete: {name}",
            _ => $"Complete via: {name}",
        };
    }
}
