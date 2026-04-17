using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Position;
using AdventureGuide.Resolution;

namespace AdventureGuide.UI.Tree;

public sealed class SpecTreeProjector
{
    private const byte EdgeDropsItem  = (byte)EdgeType.DropsItem;
    private const byte EdgeSellsItem  = (byte)EdgeType.SellsItem;
    private const byte EdgeGivesItem  = (byte)EdgeType.GivesItem;
    private const byte EdgeContains   = (byte)EdgeType.Contains;
    private const byte EdgeYieldsItem = (byte)EdgeType.YieldsItem;
    private const byte EdgeProduces   = (byte)EdgeType.Produces;

    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly UnlockPredicateEvaluator _unlocks;
    private readonly ZoneRouter? _zoneRouter;
    private readonly Func<string> _currentSceneProvider;

    public SpecTreeProjector(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks,
        ZoneRouter? zoneRouter,
        Func<string>? currentSceneProvider = null)
    {
        _guide = guide;
        _phases = phases;
        _unlocks = unlocks;
        _zoneRouter = zoneRouter;
        _currentSceneProvider = currentSceneProvider ?? (() => string.Empty);
    }

    public IReadOnlyList<SpecTreeRef> GetRootChildren(int questIndex)
    {
        return GetQuestChildren(questIndex, new[] { _guide.QuestNodeId(questIndex) });
    }

    public IReadOnlyList<SpecTreeRef> GetChildren(SpecTreeRef parent)
    {
        if (HasAncestryCycle(parent))
            return Array.Empty<SpecTreeRef>();
        if (parent.Kind == SpecTreeKind.Group)
            return FilterVisible(parent.SyntheticChildren ?? Array.Empty<SpecTreeRef>());

        if (parent.Kind == SpecTreeKind.Prerequisite)
        {
            int prereqQuestIndex = _guide.FindQuestIndex(parent.NodeId);
            return prereqQuestIndex >= 0
                ? FilterVisible(GetQuestChildren(prereqQuestIndex, parent.Ancestry))
                : Array.Empty<SpecTreeRef>();
        }

        return FilterVisible(GetNodeChildren(parent));
    }

    private IReadOnlyList<SpecTreeRef> GetNodeChildren(SpecTreeRef parent)
    {
        var node = _guide.GetNode(parent.NodeId);
        if (parent.Kind == SpecTreeKind.Source && node.Type == NodeType.Recipe)
            return GetRecipeMaterialChildren(parent.QuestIndex, parent.NodeId, parent.Ancestry);

        if ((parent.Kind == SpecTreeKind.Item || parent.Kind is SpecTreeKind.Giver or SpecTreeKind.Completer or SpecTreeKind.Step)
            && node.Type is NodeType.Item or NodeType.Book)
        {
            return GetItemChildren(parent.QuestIndex, parent.NodeId, parent.Ancestry);
        }

        if ((parent.Kind == SpecTreeKind.Source || parent.Kind is SpecTreeKind.Giver or SpecTreeKind.Completer)
            && node.Type == NodeType.Quest)
        {
            int questIndex = _guide.FindQuestIndex(parent.NodeId);
            return questIndex >= 0 ? GetQuestChildren(questIndex, parent.Ancestry) : Array.Empty<SpecTreeRef>();
        }

        return Array.Empty<SpecTreeRef>();
    }

    private IReadOnlyList<SpecTreeRef> GetItemChildren(int questIndex, int itemNodeId, int[] ancestry)
    {
        int itemIndex = _guide.FindItemIndex(itemNodeId);
        if (itemIndex < 0)
            return Array.Empty<SpecTreeRef>();

        var results = new List<SpecTreeRef>();
        var visibleSources = ApplyHostileDropFilter(_guide.GetItemSources(itemIndex));
        for (int i = 0; i < visibleSources.Count; i++)
            AddIfVisible(results, BuildSourceRef(questIndex, visibleSources[i], ancestry));

        foreach (var rewardEdge in _guide.InEdges(_guide.GetNodeKey(itemNodeId), EdgeType.RewardsItem))
        {
            if (_guide.TryGetNodeId(rewardEdge.Source, out int rewardQuestId))
                AddIfVisible(results, BuildRewardQuestSourceRef(questIndex, rewardQuestId, ancestry));
        }

        return results;
    }

    private bool ItemHasPotentialChildren(int itemNodeId)
    {
        int itemIndex = _guide.FindItemIndex(itemNodeId);
        if (itemIndex < 0)
            return false;
        if (_guide.GetItemSources(itemIndex).Length > 0)
            return true;
        return _guide.InEdges(_guide.GetNodeKey(itemNodeId), EdgeType.RewardsItem).Count > 0;
    }



    public IReadOnlyList<SpecTreeRef> GetUnlockChildren(SpecTreeRef parent)
    {
        if (HasAncestryCycle(parent))
            return Array.Empty<SpecTreeRef>();

        var groups = new List<IReadOnlyList<UnlockConditionEntry>>();
        groups.AddRange(_unlocks.GetBlockingRequirementGroups(parent.NodeId));
        if (parent.BlockedByNodeId is int blockedByNodeId && blockedByNodeId != parent.NodeId)
            groups.AddRange(_unlocks.GetBlockingRequirementGroups(blockedByNodeId));
        if (groups.Count == 0)
            return Array.Empty<SpecTreeRef>();
        if (groups.Count == 1)
            return FilterVisible(BuildUnlockGroupChildren(parent.QuestIndex, parent.Ancestry, groups[0]));

        var options = new List<SpecTreeRef>();
        for (int i = 0; i < groups.Count; i++)
        {
            var children = FilterVisible(BuildUnlockGroupChildren(parent.QuestIndex, parent.Ancestry, groups[i]));
            if (children.Count == 0)
                continue;
            if (groups[i].Count > 1)
                options.Add(BuildGroupRef(parent.QuestIndex, "All of:", parent.Ancestry, children.ToArray()));
            else
                options.AddRange(children);
        }

        if (options.Count <= 1)
            return options;

        return new[] { BuildGroupRef(parent.QuestIndex, "Any of:", parent.Ancestry, options.ToArray()) };
    }


    private void AppendUnlockChildren(int nodeId, int questIndex, int[] ancestry, List<SpecTreeRef> results)
    {
        if (!_guide.TryGetUnlockPredicate(nodeId, out var predicate))
            return;

        foreach (var condition in predicate.Conditions)
        {
            if (ancestry.Contains(condition.SourceId))
                continue;
            results.Add(BuildUnlockConditionRef(questIndex, condition, ancestry));
        }
    }

    private SpecTreeRef BuildPrerequisiteRef(int questIndex, int prereqId) =>
        BuildPrerequisiteRef(questIndex, prereqId, Array.Empty<int>());

    private SpecTreeRef BuildPrerequisiteRef(int questIndex, int prereqId, int[] ancestry)
    {
        string name = _guide.GetDisplayName(prereqId);
        int prereqQuestIndex = _guide.FindQuestIndex(prereqId);
        bool done = prereqQuestIndex >= 0 && _phases.IsCompleted(prereqQuestIndex);
        return new SpecTreeRef(
            prereqId,
            SpecTreeKind.Prerequisite,
            questIndex,
            name,
            $"Requires: {name}",
            done,
            false,
            ancestry: AppendAncestry(ancestry, prereqId));
    }

    private SpecTreeRef BuildGiverRef(int questIndex, int giverId) =>
        BuildGiverRef(questIndex, giverId, Array.Empty<int>());

    private SpecTreeRef BuildGiverRef(int questIndex, int giverId, int[] ancestry)
    {
        string name = _guide.GetDisplayName(giverId);
        FindGiverInteraction(questIndex, giverId, out _, out string? keyword);
        int? blockedByNodeId = FindBlockingZoneLineNodeId(_guide.GetScene(giverId));
        bool isBlocked = _unlocks.Evaluate(giverId) == UnlockResult.Blocked || blockedByNodeId.HasValue;
        return new SpecTreeRef(
            giverId,
            SpecTreeKind.Giver,
            questIndex,
            name,
            FormatAssignmentLabel(giverId, name, keyword),
            false,
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, giverId));
    }

    private SpecTreeRef BuildRequiredItemRef(int questIndex, ItemReq requirement) =>
        BuildItemRequirementRef(questIndex, requirement.ItemId, requirement.Quantity, Array.Empty<int>());

    private SpecTreeRef BuildItemRequirementRef(int questIndex, int itemId, int quantity, int[] ancestry)
    {
        string name = _guide.GetDisplayName(itemId);
        int itemIndex = _guide.FindItemIndex(itemId);
        int have = itemIndex >= 0 ? _phases.GetItemCount(itemIndex) : 0;
        string label = quantity > 1
            ? $"Collect: {name} ({have}/{quantity})"
            : $"Collect: {name}";
        return new SpecTreeRef(
            itemId,
            SpecTreeKind.Item,
            questIndex,
            name,
            label,
            have >= quantity,
            false,
            ancestry: AppendAncestry(ancestry, itemId));
    }

    private SpecTreeRef BuildStepRef(int questIndex, StepEntry step) =>
        BuildStepRef(questIndex, step, Array.Empty<int>());

    private SpecTreeRef BuildStepRef(int questIndex, StepEntry step, int[] ancestry)
    {
        string name = _guide.GetDisplayName(step.TargetId);
        int? blockedByNodeId = FindBlockingZoneLineNodeId(_guide.GetScene(step.TargetId));
        bool isBlocked = _unlocks.Evaluate(step.TargetId) == UnlockResult.Blocked || blockedByNodeId.HasValue;
        return new SpecTreeRef(
            step.TargetId,
            SpecTreeKind.Step,
            questIndex,
            name,
            FormatStepLabel(step, name),
            false,
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, step.TargetId));
    }

    private SpecTreeRef BuildCompleterRef(int questIndex, int completerId) =>
        BuildCompleterRef(questIndex, completerId, Array.Empty<int>());

    private SpecTreeRef BuildCompleterRef(int questIndex, int completerId, int[] ancestry)
    {
        string name = _guide.GetDisplayName(completerId);
        FindCompletionInteraction(questIndex, completerId, out _, out string? keyword);
        int? blockedByNodeId = FindBlockingZoneLineNodeId(_guide.GetScene(completerId));
        bool isBlocked = _unlocks.Evaluate(completerId) == UnlockResult.Blocked || blockedByNodeId.HasValue;
        return new SpecTreeRef(
            completerId,
            SpecTreeKind.Completer,
            questIndex,
            name,
            FormatCompletionLabel(completerId, name, keyword),
            false,
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, completerId));
    }

    private SpecTreeRef BuildSourceRef(int questIndex, SourceSiteEntry source) =>
        BuildSourceRef(questIndex, source, Array.Empty<int>());

    private SpecTreeRef BuildSourceRef(int questIndex, SourceSiteEntry source, int[] ancestry)
    {
        string name = _guide.GetDisplayName(source.SourceId);
        int? blockedByNodeId = FindBlockingZoneLineNodeId(_guide.GetSourceScene(source));
        bool isBlocked = _unlocks.Evaluate(source.SourceId) == UnlockResult.Blocked || blockedByNodeId.HasValue;
        return new SpecTreeRef(
            source.SourceId,
            SpecTreeKind.Source,
            questIndex,
            name,
            FormatSourceLabel(source, name),
            false,
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, source.SourceId),
            requiresVisibleChildren: source.SourceType == (byte)NodeType.Recipe);

    }

    private SpecTreeRef BuildRewardQuestSourceRef(int questIndex, int rewardQuestId, int[] ancestry)
    {
        string name = _guide.GetDisplayName(rewardQuestId);
        return new SpecTreeRef(
            rewardQuestId,
            SpecTreeKind.Source,
            questIndex,
            name,
            $"Complete {name}",
            false,
            false,
            ancestry: AppendAncestry(ancestry, rewardQuestId),
            requiresVisibleChildren: true);

    }

    private SpecTreeRef BuildUnlockConditionRef(int questIndex, UnlockConditionEntry condition) =>
        BuildUnlockConditionRef(questIndex, condition, Array.Empty<int>());

    private SpecTreeRef BuildUnlockConditionRef(int questIndex, UnlockConditionEntry condition, int[] ancestry)
    {
        string name = _guide.GetDisplayName(condition.SourceId);
        SpecTreeKind kind = DetermineUnlockKind(condition);
        return new SpecTreeRef(
            condition.SourceId,
            kind,
            questIndex,
            name,
            $"Requires: {name}",
            IsUnlockConditionSatisfied(condition),
            false,
            ancestry: AppendAncestry(ancestry, condition.SourceId),
            requiresVisibleChildren: kind == SpecTreeKind.Item && ItemHasPotentialChildren(condition.SourceId));


    }

    private List<SourceSiteEntry> ApplyHostileDropFilter(ReadOnlySpan<SourceSiteEntry> sources)
    {
        bool hasHostileDrop = false;
        for (int i = 0; i < sources.Length && !hasHostileDrop; i++)
        {
            if (sources[i].EdgeType == EdgeDropsItem && IsHostileDropSource(sources[i]))
                hasHostileDrop = true;
        }

        var visible = new List<SourceSiteEntry>(sources.Length);
        for (int i = 0; i < sources.Length; i++)
        {
            var source = sources[i];
            if (hasHostileDrop && source.EdgeType == EdgeDropsItem && !IsHostileDropSource(source))
                continue;
            visible.Add(source);
        }

        return visible;
    }

    private bool IsHostileDropSource(SourceSiteEntry source)
    {
        if (source.EdgeType != EdgeDropsItem)
            return false;

        var node = _guide.GetNode(source.SourceId);
        return !node.IsFriendly;
    }

    private int? FindBlockingZoneLineNodeId(string? targetScene)
    {
        if (_zoneRouter == null)
            return null;

        string currentScene = _currentSceneProvider();
        if (string.IsNullOrWhiteSpace(currentScene) || string.IsNullOrWhiteSpace(targetScene))
            return null;
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return null;

        var lockedHop = _zoneRouter.FindFirstLockedHop(currentScene, targetScene);
        if (lockedHop == null)
            return null;

        return _guide.TryGetNodeId(lockedHop.ZoneLineKey, out int zoneLineNodeId)
            ? zoneLineNodeId
            : null;
    }

    private SpecTreeKind DetermineUnlockKind(UnlockConditionEntry condition)
    {
        if (condition.CheckType == 1)
            return SpecTreeKind.Item;

        return _guide.GetNode(condition.SourceId).Type == NodeType.Quest
            ? SpecTreeKind.Prerequisite
            : SpecTreeKind.Source;
    }

    private bool IsUnlockConditionSatisfied(UnlockConditionEntry condition)
    {
        if (condition.CheckType == 0)
        {
            int questIndex = _guide.FindQuestIndex(condition.SourceId);
            return questIndex >= 0 && _phases.IsCompleted(questIndex);
        }

        int itemIndex = _guide.FindItemIndex(condition.SourceId);
        return itemIndex >= 0 && _phases.GetItemCount(itemIndex) > 0;
    }

    private IReadOnlyList<SpecTreeRef> GetQuestChildren(int questIndex, int[] ancestry)
    {
        var results = new List<SpecTreeRef>();
        foreach (int prereqId in _guide.PrereqQuestIds(questIndex))
            AddIfVisible(results, BuildPrerequisiteRef(questIndex, prereqId, ancestry));
        foreach (int giverId in _guide.GiverIds(questIndex))
            AddIfVisible(results, BuildGiverRef(questIndex, giverId, ancestry));
        foreach (var requirement in _guide.RequiredItems(questIndex))
            AddIfVisible(results, BuildItemRequirementRef(questIndex, requirement.ItemId, requirement.Quantity, ancestry));
        foreach (var step in _guide.Steps(questIndex))
            AddIfVisible(results, BuildStepRef(questIndex, step, ancestry));
        foreach (int completerId in _guide.CompleterIds(questIndex))
            AddIfVisible(results, BuildCompleterRef(questIndex, completerId, ancestry));
        return results;
    }

    private IReadOnlyList<SpecTreeRef> GetRecipeMaterialChildren(int questIndex, int recipeNodeId, int[] ancestry)
    {
        var results = new List<SpecTreeRef>();
        foreach (var materialEdge in _guide.OutEdges(_guide.GetNodeKey(recipeNodeId), EdgeType.RequiresMaterial))
        {
            if (!_guide.TryGetNodeId(materialEdge.Target, out int materialId))
                continue;
            AddIfVisible(results, BuildItemRequirementRef(questIndex, materialId, materialEdge.Quantity ?? 1, ancestry));
        }
        return results;
    }

    private void AddIfVisible(List<SpecTreeRef> results, SpecTreeRef candidate)
    {
        if (!IsMeaningfullyVisible(candidate))
            return;
        results.Add(candidate);
    }

    private IReadOnlyList<SpecTreeRef> FilterVisible(IEnumerable<SpecTreeRef> candidates)
    {
        var results = new List<SpecTreeRef>();
        foreach (var candidate in candidates)
            AddIfVisible(results, candidate);
        return results;
    }

    private bool IsMeaningfullyVisible(SpecTreeRef candidate)
    {
        bool hasVisibleDescendants = GetUnlockChildren(candidate).Count > 0 || GetChildren(candidate).Count > 0;
        if (RequiresVisibleChildren(candidate))
            return candidate.IsCompleted || hasVisibleDescendants;
        return !candidate.IsBlocked || hasVisibleDescendants;
    }

    private bool RequiresVisibleChildren(SpecTreeRef candidate)
    {
        if (candidate.RequiresVisibleChildren)
            return true;
        if (candidate.Kind == SpecTreeKind.Source)
        {
            var node = _guide.GetNode(candidate.NodeId);
            return node.Type is NodeType.Quest or NodeType.Recipe;
        }
        return false;
    }


    private static bool HasAncestryCycle(SpecTreeRef candidate)
    {
        if (candidate.Ancestry.Length < 2)
            return false;
        for (int i = 0; i < candidate.Ancestry.Length - 1; i++)
        {
            if (candidate.Ancestry[i] == candidate.NodeId)
                return true;
        }
        return false;
    }


    private SpecTreeRef[] BuildUnlockGroupChildren(int questIndex, int[] ancestry, IReadOnlyList<UnlockConditionEntry> conditions)
    {
        var children = new List<SpecTreeRef>();
        for (int i = 0; i < conditions.Count; i++)
        {
            if (ancestry.Contains(conditions[i].SourceId))
                continue;
            children.Add(BuildUnlockConditionRef(questIndex, conditions[i], ancestry));
        }
        return children.ToArray();
    }

    private SpecTreeRef BuildGroupRef(int questIndex, string label, int[] ancestry, SpecTreeRef[] children)
    {
        int syntheticId = -Math.Abs(HashCode.Combine(label, questIndex, ancestry.Length, children.Length));
        return new SpecTreeRef(
            syntheticId,
            SpecTreeKind.Group,
            questIndex,
            label,
            label,
            false,
            false,
            ancestry: ancestry,
            syntheticChildren: children,
            requiresVisibleChildren: true);

    }

    private static int[] AppendAncestry(int[] ancestry, int nodeId)
    {
        if (ancestry.Length > 0 && ancestry[^1] == nodeId)
            return ancestry;

        var next = new int[ancestry.Length + 1];
        Array.Copy(ancestry, next, ancestry.Length);
        next[^1] = nodeId;
        return next;
    }

    private string FormatAssignmentLabel(int nodeId, string name, string? keyword)
    {
        return _guide.GetNode(nodeId).Type switch
        {
            NodeType.Item => $"Read {name}",
            NodeType.Zone => $"Enter {name}",
            NodeType.Quest => $"Complete {name}",
            _ => FormatKeywordLabel("Talk to ", name, keyword),
        };
    }

    private string FormatCompletionLabel(int nodeId, string name, string? keyword)
    {
        return _guide.GetNode(nodeId).Type switch
        {
            NodeType.Character => FormatKeywordLabel("Turn in to ", name, keyword),
            NodeType.Item => $"Read {name}",
            NodeType.Zone => $"Enter {name}",
            NodeType.ZoneLine => $"Travel to {name}",
            NodeType.Quest => $"Complete {name}",
            _ => $"Complete via: {name}",
        };
    }

    private string FormatStepLabel(StepEntry step, string name)
    {
        return StepLabels.Format(step.StepType, name);
    }

    private string FormatSourceLabel(SourceSiteEntry source, string name)
    {
        return source.EdgeType switch
        {
            EdgeDropsItem => $"Drops from: {name}",
            EdgeSellsItem => $"Vendor: {name}",
            EdgeGivesItem => FormatKeywordLabel("Talk to ", name, source.Keyword),
            EdgeContains => $"Collect from: {name}",
            EdgeProduces => $"Crafted via: {name}",
            EdgeYieldsItem => FormatYieldLabel(source, name),
            _ => name,
        };
    }

    private string FormatYieldLabel(SourceSiteEntry source, string name)
    {
        return source.SourceType switch
        {
            (byte)NodeType.MiningNode => $"Mine at: {name}",
            _ => _guide.GetNode(source.SourceId).Type == NodeType.Water
                ? $"Fish at: {name}"
                : $"Collect from: {name}",
        };
    }

    private static string FormatKeywordLabel(string prefix, string name, string? keyword)
    {
        return string.IsNullOrEmpty(keyword)
            ? $"{prefix}{name}"
            : $"{prefix}{name} — say \"{keyword}\"";
    }

    private void FindGiverInteraction(int questIndex, int giverId, out byte interactionType, out string? keyword)
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        foreach (var blueprint in _guide.GiverBlueprints)
        {
            if (blueprint.QuestId == questNodeId && blueprint.CharacterId == giverId)
            {
                interactionType = blueprint.InteractionType;
                keyword = interactionType == 1 ? blueprint.Keyword : null;
                return;
            }
        }

        interactionType = 0;
        keyword = null;
    }

    private void FindCompletionInteraction(int questIndex, int completerId, out byte interactionType, out string? keyword)
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        foreach (var blueprint in _guide.CompletionBlueprints)
        {
            if (blueprint.QuestId == questNodeId && blueprint.CharacterId == completerId)
            {
                interactionType = blueprint.InteractionType;
                keyword = interactionType == 1 ? blueprint.Keyword : null;
                return;
            }
        }

        interactionType = 0;
        keyword = null;
    }
}
