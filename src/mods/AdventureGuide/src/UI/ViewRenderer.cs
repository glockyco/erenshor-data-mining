using AdventureGuide.Navigation;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.UI.Tree;
using ImGuiNET;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.UI;

public sealed class ViewRenderer
{
    private readonly CompiledGuideModel _guide;
    private readonly GameState _state;
    private readonly NavigationSet _navSet;
    private readonly QuestStateTracker _tracker;
    private readonly TrackerState _trackerState;
    private readonly SpecTreeProjector _specProjector;
    private readonly Dictionary<int, QuestResolutionRecord> _lastRecordByQuest = new();
    private readonly Dictionary<int, IReadOnlyList<SpecTreeRef>> _cachedRootChildrenByQuest = new();
    private readonly Dictionary<string, IReadOnlyList<SpecTreeRef>> _cachedChildren = new(
        StringComparer.Ordinal
    );
    private readonly Dictionary<string, IReadOnlyList<SpecTreeRef>> _cachedUnlockChildren = new(
        StringComparer.Ordinal
    );

    public ViewRenderer(
        CompiledGuideModel guide,
        GameState state,
        NavigationSet navSet,
        QuestStateTracker tracker,
        TrackerState trackerState,
        SpecTreeProjector specProjector
    )
    {
        _guide = guide;
        _state = state;
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

        int questNodeId = _guide.QuestNodeId(questIndex.Value);
        string questKey = _guide.GetNodeKey(questNodeId);
        var quest = _guide.GetNode(questKey);
        if (quest == null)
        {
            DrawNotice("No guide data available for this quest.");
            return;
        }

        DrawHeader(quest, questKey);

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();

        var rootChildren = GetRootChildrenForDetail(questIndex.Value);
        string? completionFallback = GetCompletionFallbackNotice(_guide, quest);
        var sections = BuildDetailSections(rootChildren);
        if (sections.Count == 0 && completionFallback == null)
        {
            DrawNotice("No guide data available for this quest.");
        }
        else
        {
            for (int sectionIndex = 0; sectionIndex < sections.Count; sectionIndex++)
            {
                var section = sections[sectionIndex];
                if (!ImGui.CollapsingHeader(section.Label, ImGuiTreeNodeFlags.DefaultOpen))
                    continue;

                ImGui.Indent(Theme.IndentWidth);
                if (section.ShowAlternativesLabel)
                    DrawAlternativesLabel();

                for (int rootIndex = 0; rootIndex < section.Roots.Count; rootIndex++)
                {
                    ImGui.PushID($"spec_section_{sectionIndex}_{rootIndex}");
                    DrawSpecTreeRef(section.Roots[rootIndex]);
                    ImGui.PopID();
                }
                ImGui.Unindent(Theme.IndentWidth);
            }

            if (completionFallback != null)
            {
                ImGui.Spacing();
                DrawNoticeGroup("How to complete", completionFallback);
            }
        }

        ImGui.Spacing();
        DrawRewards(quest);
    }

    internal IReadOnlyList<SpecTreeRef> GetRootChildrenForDetail(int questIndex)
    {
        var record = EnsureDetailProjectionCacheCurrent(questIndex);
        if (_cachedRootChildrenByQuest.TryGetValue(questIndex, out var cachedRoots))
            return cachedRoots;

        cachedRoots = _specProjector.GetRootChildren(record);
        _cachedRootChildrenByQuest[questIndex] = cachedRoots;
        return cachedRoots;
    }

    internal IReadOnlyList<SpecTreeRef> GetUnlockChildrenForDetail(SpecTreeRef treeRef)
    {
        EnsureDetailProjectionCacheCurrent(treeRef.QuestIndex);
        string cacheKey = BuildDetailProjectionKey("unlock", treeRef);
        if (_cachedUnlockChildren.TryGetValue(cacheKey, out var cachedChildren))
            return cachedChildren;

        cachedChildren = _specProjector.GetUnlockChildren(treeRef);
        _cachedUnlockChildren[cacheKey] = cachedChildren;
        return cachedChildren;
    }

    internal IReadOnlyList<SpecTreeRef> GetChildrenForDetail(SpecTreeRef treeRef)
    {
        EnsureDetailProjectionCacheCurrent(treeRef.QuestIndex);
        string cacheKey = BuildDetailProjectionKey("children", treeRef);
        if (_cachedChildren.TryGetValue(cacheKey, out var cachedChildren))
            return cachedChildren;

        cachedChildren = _specProjector.GetChildren(treeRef);
        _cachedChildren[cacheKey] = cachedChildren;
        return cachedChildren;
    }

    private QuestResolutionRecord EnsureDetailProjectionCacheCurrent(int questIndex)
    {
        var record = _specProjector.GetRecord(questIndex);
        if (
            _lastRecordByQuest.TryGetValue(questIndex, out var cachedRecord)
            && ReferenceEquals(cachedRecord, record)
        )
            return record;

        InvalidateDetailProjectionCacheFor(questIndex);
        _lastRecordByQuest[questIndex] = record;
        return record;
    }

    private void InvalidateDetailProjectionCacheFor(int questIndex)
    {
        _cachedRootChildrenByQuest.Remove(questIndex);
        RemoveDetailProjectionEntries(_cachedChildren, questIndex, "children");
        RemoveDetailProjectionEntries(_cachedUnlockChildren, questIndex, "unlock");
        _specProjector.ResetProjectionCaches(1, full: false);
    }

    private static void RemoveDetailProjectionEntries(
        Dictionary<string, IReadOnlyList<SpecTreeRef>> cache,
        int questIndex,
        string scope
    )
    {
        string prefix = $"{scope}|{questIndex}|";
        var keys = cache.Keys.Where(key => key.StartsWith(prefix, StringComparison.Ordinal)).ToArray();
        for (int i = 0; i < keys.Length; i++)
            cache.Remove(keys[i]);
    }

    private static string BuildDetailProjectionKey(string scope, SpecTreeRef treeRef)
    {
        return string.Join(
            "|",
            scope,
            treeRef.QuestIndex.ToString(),
            ((byte)treeRef.Kind).ToString(),
            treeRef.StableId,
            treeRef.GraphNodeId?.ToString() ?? string.Empty,
            treeRef.Label,
            treeRef.IsCompleted ? "1" : "0",
            treeRef.IsBlocked ? "1" : "0",
            treeRef.BlockedByGraphNodeId?.ToString() ?? string.Empty,
            treeRef.RequiresVisibleChildren ? "1" : "0",
            string.Join(",", treeRef.Ancestry)
        );
    }

    private void DrawSpecTreeRef(SpecTreeRef treeRef)
    {
        var node = ResolveGraphNode(treeRef);
        bool navigable = node != null && IsNavigable(node);
        var unlockChildren = GetUnlockChildrenForDetail(treeRef);
        var children = GetChildrenForDetail(treeRef);

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
            bool open = ImGui.TreeNodeEx($"{treeRef.Label}###{treeRef.Kind}:{treeRef.StableId}");
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

    internal Node? ResolveGraphNode(SpecTreeRef treeRef)
    {
        if (treeRef.GraphNodeId is not int graphNodeId)
            return null;

        string key = _guide.GetNodeKey(graphNodeId);
        return _guide.GetNode(key);
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
                if (tracked)
                    _trackerState.Untrack(dbName);
                else
                    _trackerState.Track(dbName);
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
            if (meta.Length > 0)
                meta += "  ·  ";
            meta += quest.Zone;
        }
        if (quest.Repeatable)
        {
            if (meta.Length > 0)
                meta += "  ·  ";
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

    internal readonly struct DetailSection
    {
        public DetailSection(
            string label,
            IReadOnlyList<SpecTreeRef> roots,
            bool showAlternativesLabel
        )
        {
            Label = label;
            Roots = roots;
            ShowAlternativesLabel = showAlternativesLabel;
        }

        public string Label { get; }
        public IReadOnlyList<SpecTreeRef> Roots { get; }
        public bool ShowAlternativesLabel { get; }
    }

    internal static IReadOnlyList<DetailSection> BuildDetailSections(
        IReadOnlyList<SpecTreeRef> roots
    )
    {
        var sections = new List<DetailSection>();
        AddSection(
            sections,
            "Prerequisites",
            roots.Where(root => root.Kind == SpecTreeKind.Prerequisite).ToArray()
        );
        var acceptRoots = roots.Where(root => root.Kind == SpecTreeKind.Giver).ToArray();
        AddSection(sections, "Accept", acceptRoots, acceptRoots.Length > 1);
        AddSection(
            sections,
            "Objectives",
            roots.Where(root => root.Kind is SpecTreeKind.Item or SpecTreeKind.Step).ToArray()
        );
        var turnInRoots = roots.Where(root => root.Kind == SpecTreeKind.Completer).ToArray();
        AddSection(sections, "Turn in", turnInRoots, turnInRoots.Length > 1);
        return sections;
    }

    private static void AddSection(
        List<DetailSection> sections,
        string label,
        IReadOnlyList<SpecTreeRef> roots,
        bool showAlternativesLabel = false
    )
    {
        if (roots.Count == 0)
            return;

        sections.Add(new DetailSection(label, roots, showAlternativesLabel));
    }

    private static void DrawAlternativesLabel()
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextUnformatted("Any of:");
        ImGui.PopStyleColor();
    }

    internal static string? GetCompletionFallbackNotice(CompiledGuideModel guide, Node quest) =>
        guide.OutEdges(quest.Key, EdgeType.CompletedBy).Count == 0
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
                badge = "[AVAILABLE]";
                color = Theme.QuestImplicit;
                break;
            default:
                badge = "[AVAILABLE]";
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
        bool hasNodeRewards =
            quest.XpReward is > 0 || quest.GoldReward is > 0 || quest.RewardItemKey != null;

        var rewardEdges = _guide.OutEdges(quest.Key, EdgeType.RewardsItem);
        var chainEdges = _guide.OutEdges(quest.Key, EdgeType.ChainsTo);
        var alsoEdges = _guide.OutEdges(quest.Key, EdgeType.AlsoCompletes);
        var zoneLineEdges = _guide.OutEdges(quest.Key, EdgeType.UnlocksZoneLine);
        var charEdges = _guide.OutEdges(quest.Key, EdgeType.UnlocksCharacter);
        var factionEdges = _guide.OutEdges(quest.Key, EdgeType.AffectsFaction);
        var vendorEdges = _guide.OutEdges(quest.Key, EdgeType.UnlocksVendorItem);

        bool hasEdgeRewards =
            rewardEdges.Count > 0
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
            bool variantGrouped =
                rewardEdges.Any(e => e.Group != null)
                && rewardEdges.Select(e => e.Group).Distinct().Count() > 1;
            if (variantGrouped)
            {
                foreach (var edge in rewardEdges)
                {
                    var itemNode = _guide.GetNode(edge.Target);
                    if (itemNode != null)
                        ImGui.Text(itemNode.DisplayName);
                }
            }
            else
            {
                var shown = new HashSet<string>(StringComparer.Ordinal);
                for (int i = 0; i < rewardEdges.Count; i++)
                {
                    if (!shown.Add(rewardEdges[i].Target))
                        continue;
                    var itemNode = _guide.GetNode(rewardEdges[i].Target);
                    if (itemNode != null)
                        ImGui.Text(itemNode.DisplayName);
                }
            }
        }
        if (rewardEdges.Count == 0 && quest.RewardItemKey != null)
        {
            var itemNode = _guide.GetNode(quest.RewardItemKey);
            ImGui.Text(itemNode?.DisplayName ?? quest.RewardItemKey);
        }

        for (int i = 0; i < zoneLineEdges.Count; i++)
        {
            var zlNode = _guide.GetNode(zoneLineEdges[i].Target);
            if (zlNode == null)
                continue;
            string dest = zlNode.DestinationDisplay ?? zlNode.DisplayName;
            string from = zlNode.Zone ?? zlNode.Scene ?? "";
            if (from.Length > 0)
                ImGui.Text($"Opens path: {from} > {dest}");
            else
                ImGui.Text($"Opens path to {dest}");
        }

        for (int i = 0; i < charEdges.Count; i++)
        {
            var charNode = _guide.GetNode(charEdges[i].Target);
            if (charNode == null)
                continue;
            string text =
                charNode.Zone != null
                    ? $"Enables {charNode.DisplayName} in {charNode.Zone}"
                    : $"Enables {charNode.DisplayName}";
            ImGui.Text(text);
        }

        for (int i = 0; i < vendorEdges.Count; i++)
        {
            var edge = vendorEdges[i];
            var itemNode = _guide.GetNode(edge.Target);
            if (itemNode == null)
                continue;
            string vendorName = "vendor";
            if (edge.Note != null)
            {
                var vendorNode = _guide.GetNode(edge.Note);
                if (vendorNode != null)
                    vendorName = vendorNode.DisplayName;
            }
            ImGui.Text($"Unlocks {itemNode.DisplayName} at {vendorName}");
        }

        for (int i = 0; i < chainEdges.Count; i++)
        {
            var nextQuest = _guide.GetNode(chainEdges[i].Target);
            if (nextQuest == null)
                continue;
            if (ImGui.Selectable($"Chains to: {nextQuest.DisplayName}###chain_{nextQuest.Key}"))
            {
                if (nextQuest.DbName != null)
                    _tracker.SelectQuest(nextQuest.DbName);
            }
        }

        for (int i = 0; i < alsoEdges.Count; i++)
        {
            var otherQuest = _guide.GetNode(alsoEdges[i].Target);
            if (otherQuest == null)
                continue;
            if (
                ImGui.Selectable(
                    $"Also completes: {otherQuest.DisplayName}###also_{otherQuest.Key}"
                )
            )
            {
                if (otherQuest.DbName != null)
                    _tracker.SelectQuest(otherQuest.DbName);
            }
        }

        for (int i = 0; i < factionEdges.Count; i++)
        {
            var edge = factionEdges[i];
            var factionNode = _guide.GetNode(edge.Target);
            if (factionNode == null)
                continue;
            int amount = edge.Amount ?? 0;
            string sign = amount >= 0 ? "+" : "";
            ImGui.Text($"{factionNode.DisplayName}: {sign}{amount}");
        }

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);
    }

    private static string FormatKeyword(string prefix, string name, string? keyword) =>
        !string.IsNullOrEmpty(keyword) ? $"{prefix}{name} — say \"{keyword}\"" : $"{prefix}{name}";
}
