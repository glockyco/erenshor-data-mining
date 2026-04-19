using System.Diagnostics;
using AdventureGuide.CompiledGuide;
using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.State;

namespace AdventureGuide.UI.Tree;

public sealed class SpecTreeProjector
{
    private const byte EdgeDropsItem = (byte)EdgeType.DropsItem;
    private const byte EdgeSellsItem = (byte)EdgeType.SellsItem;
    private const byte EdgeGivesItem = (byte)EdgeType.GivesItem;
    private const byte EdgeContains = (byte)EdgeType.Contains;
    private const byte EdgeYieldsItem = (byte)EdgeType.YieldsItem;
    private const byte EdgeProduces = (byte)EdgeType.Produces;

    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly GuideReader _reader;
    private readonly QuestPhaseTracker _phases;
    private readonly QuestStateTracker _questTracker;
    private readonly Func<string> _currentSceneProvider;
    private readonly DiagnosticsCore? _diagnostics;

    private readonly Dictionary<string, IReadOnlyList<SpecTreeRef>> _childCache = new(
        StringComparer.Ordinal
    );
    private readonly Dictionary<string, IReadOnlyList<SpecTreeRef>> _unlockCache = new(
        StringComparer.Ordinal
    );
    private readonly Dictionary<string, bool> _visibilityCache = new(StringComparer.Ordinal);
    private readonly HashSet<string> _activeProjectionKeys = new(StringComparer.Ordinal);
    private int _projectionDepth;
    private int _lastProjectedNodeCount;

    private int _lastChildCount;
    private int _lastPrunedCount;
    private int _lastCyclePruneCount;
    private int _lastInvalidatedQuestCount;
    private bool _lastInvalidationWasFull;

    internal SpecTreeProjector(
        CompiledGuide.CompiledGuide guide,
        GuideReader reader,
        QuestPhaseTracker phases,
        QuestStateTracker questTracker,
        Func<string>? currentSceneProvider = null,
        DiagnosticsCore? diagnostics = null
    )
    {
        _guide = guide;
        _reader = reader;
        _phases = phases;
        _questTracker = questTracker;
        _currentSceneProvider = currentSceneProvider ?? (() => string.Empty);
        _diagnostics = diagnostics;
    }

    public IReadOnlyList<SpecTreeRef> GetRootChildren(int questIndex)
    {
        var record = GetRecord(questIndex);
        return GetRootChildren(record);
    }

    internal QuestResolutionRecord GetRecord(int questIndex)
    {
        string questKey = _guide.GetNodeKey(_guide.QuestNodeId(questIndex));
        return _reader.ReadQuestResolution(questKey, _currentSceneProvider());
    }

    internal IReadOnlyList<SpecTreeRef> GetRootChildren(QuestResolutionRecord record)
    {
        var token = _diagnostics?.BeginSpan(
            DiagnosticSpanKind.SpecTreeProjectRoot,
            DiagnosticsContext.Root(DiagnosticTrigger.Unknown),
            primaryKey: record.QuestKey
        );
        long startTick = Stopwatch.GetTimestamp();
        EnterProjection();
        try
        {
            _lastChildCount = 0;
            _lastPrunedCount = 0;
            _lastCyclePruneCount = 0;
            int questIndex = FindQuestIndex(record.QuestKey);
            var roots = GetQuestChildren(record, questIndex, new[] { _guide.QuestNodeId(questIndex) });

            _lastProjectedNodeCount = roots.Count;
            return roots;
        }
        finally
        {
            ExitProjection();
            if (token != null)
                _diagnostics!.EndSpan(
                    token.Value,
                    Stopwatch.GetTimestamp() - startTick,
                    value0: _lastProjectedNodeCount,
                    value1: _lastCyclePruneCount
                );
        }
    }

    public IReadOnlyList<SpecTreeRef> GetChildren(SpecTreeRef parent)
    {
        EnterProjection();
        try
        {
            return GetChildrenCore(parent);
        }
        finally
        {
            ExitProjection();
        }
    }

    private IReadOnlyList<SpecTreeRef> GetChildrenCore(SpecTreeRef parent)
    {
        if (HasAncestryCycle(parent))
            return Array.Empty<SpecTreeRef>();

        string cacheKey = BuildProjectionKey("children", parent);
        if (_childCache.TryGetValue(cacheKey, out var cachedChildren))
            return cachedChildren;
        if (!_activeProjectionKeys.Add(cacheKey))
        {
            _lastCyclePruneCount++;
            return Array.Empty<SpecTreeRef>();
        }

        var record = GetRecord(parent.QuestIndex);
        try
        {
            IReadOnlyList<SpecTreeRef> children;
            if (parent.Kind == SpecTreeKind.Group)
                children = FilterVisible(parent.SyntheticChildren ?? Array.Empty<SpecTreeRef>());
            else if (parent.Kind == SpecTreeKind.Prerequisite)
            {
                if (parent.GraphNodeId is not int prerequisiteNodeId)
                    return Array.Empty<SpecTreeRef>();
                int prereqQuestIndex = _guide.FindQuestIndex(prerequisiteNodeId);

                children =
                    prereqQuestIndex >= 0
                        ? FilterVisible(GetQuestChildren(record, prereqQuestIndex, parent.Ancestry))
                        : Array.Empty<SpecTreeRef>();
            }
            else
            {
                children = FilterVisible(GetNodeChildren(record, parent));
            }

            _lastChildCount = children.Count;
            _childCache[cacheKey] = children;
            return children;
        }
        finally
        {
            _activeProjectionKeys.Remove(cacheKey);
        }
    }


    private IReadOnlyList<SpecTreeRef> GetNodeChildren(QuestResolutionRecord record, SpecTreeRef parent)
    {
        if (parent.GraphNodeId is not int graphNodeId)
            return Array.Empty<SpecTreeRef>();

        var node = _guide.GetNode(graphNodeId);
        if (node == null)
            return Array.Empty<SpecTreeRef>();
        if (parent.Kind == SpecTreeKind.Source && node.Type == NodeType.Recipe)
            return GetRecipeMaterialChildren(record, parent.QuestIndex, graphNodeId, parent.Ancestry);

        if (
            (
                parent.Kind == SpecTreeKind.Item
                || parent.Kind is SpecTreeKind.Giver or SpecTreeKind.Completer or SpecTreeKind.Step
            ) && node.Type is NodeType.Item or NodeType.Book
        )
        {
            return GetItemChildren(record, parent.QuestIndex, graphNodeId, parent.Ancestry);
        }

        if (
            (
                parent.Kind == SpecTreeKind.Source
                || parent.Kind is SpecTreeKind.Giver or SpecTreeKind.Completer
            )
            && node.Type == NodeType.Quest
        )
        {
            int questIndex = _guide.FindQuestIndex(graphNodeId);
            return questIndex >= 0
                ? GetQuestChildren(record, questIndex, parent.Ancestry)
                : Array.Empty<SpecTreeRef>();
        }

        return Array.Empty<SpecTreeRef>();
    }


    private IReadOnlyList<SpecTreeRef> GetItemChildren(
        QuestResolutionRecord record,
        int questIndex,
        int itemNodeId,
        int[] ancestry
    )

    {
        int itemIndex = _guide.FindItemIndex(itemNodeId);
        if (itemIndex < 0)
            return Array.Empty<SpecTreeRef>();

        var results = new List<SpecTreeRef>();
        var visibleSources = ApplyHostileDropFilter(_guide.GetItemSources(itemIndex));
        for (int i = 0; i < visibleSources.Count; i++)
            AddIfVisible(results, BuildSourceRef(record, questIndex, visibleSources[i], ancestry));

        foreach (
            var rewardEdge in _guide.InEdges(_guide.GetNodeKey(itemNodeId), EdgeType.RewardsItem)
        )
        {
            if (_guide.TryGetNodeId(rewardEdge.Source, out int rewardQuestId))
                AddIfVisible(
                    results,
                    BuildRewardQuestSourceRef(record, questIndex, rewardQuestId, ancestry)
                );
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
        EnterProjection();
        try
        {
            return GetUnlockChildrenCore(parent);
        }
        finally
        {
            ExitProjection();
        }
    }

    private IReadOnlyList<SpecTreeRef> GetUnlockChildrenCore(SpecTreeRef parent)
    {
        if (HasAncestryCycle(parent))
            return Array.Empty<SpecTreeRef>();

        string cacheKey = BuildProjectionKey("unlock", parent);
        if (_unlockCache.TryGetValue(cacheKey, out var cachedUnlocks))
            return cachedUnlocks;
        if (!_activeProjectionKeys.Add(cacheKey))
        {
            _lastCyclePruneCount++;
            return Array.Empty<SpecTreeRef>();
        }

        var record = GetRecord(parent.QuestIndex);
        try
        {
            if (parent.GraphNodeId is not int graphNodeId)
            {
                var empty = Array.Empty<SpecTreeRef>();
                _unlockCache[cacheKey] = empty;
                return empty;
            }

            var groups = new List<IReadOnlyList<UnlockConditionEntry>>();
            groups.AddRange(SpecTreeRecordState.GetBlockingRequirementGroups(_guide, _phases, _questTracker, graphNodeId));
            if (
                parent.BlockedByGraphNodeId is int blockedByNodeId
                && blockedByNodeId != graphNodeId
            )
                groups.AddRange(
                    SpecTreeRecordState.GetBlockingRequirementGroups(_guide, _phases, _questTracker, blockedByNodeId)
                );
            groups = DeduplicateUnlockGroups(groups);
            if (groups.Count == 0)
            {
                var empty = Array.Empty<SpecTreeRef>();
                _unlockCache[cacheKey] = empty;
                return empty;
            }

            IReadOnlyList<SpecTreeRef> unlocks;

            if (groups.Count == 1)
            {
                unlocks = FilterVisible(
                    BuildUnlockGroupChildren(record, parent.QuestIndex, parent.Ancestry, groups[0])
                );
            }
            else
            {
                var options = new List<SpecTreeRef>();
                for (int i = 0; i < groups.Count; i++)
                {
                    var children = FilterVisible(
                        BuildUnlockGroupChildren(record, parent.QuestIndex, parent.Ancestry, groups[i])
                    );
                    if (children.Count == 0)
                        continue;
                    if (groups[i].Count > 1)
                        options.Add(
                            BuildGroupRef(
                                record,
                                parent.QuestIndex,
                                "All of:",
                                parent.Ancestry,
                                children.ToArray()
                            )
                        );
                    else
                        options.Add(children[0]);
                }

                unlocks =
                    options.Count == 0
                        ? Array.Empty<SpecTreeRef>()
                        : new[]
                        {
                            BuildGroupRef(
                                record,
                                parent.QuestIndex,
                                "Any of:",
                                parent.Ancestry,
                                options.ToArray()
                            ),
                        };
            }

            _unlockCache[cacheKey] = unlocks;
            return unlocks;
        }
        finally
        {
            _activeProjectionKeys.Remove(cacheKey);
        }
    }


    private void AppendUnlockChildren(
        int nodeId,
        int questIndex,
        int[] ancestry,
        List<SpecTreeRef> results
    )
    {
        if (!_guide.TryGetUnlockPredicate(nodeId, out var predicate))
            return;

        foreach (var condition in predicate.Conditions)
        {
            if (ancestry.Contains(condition.SourceId))
            {
                _lastCyclePruneCount++;
                continue;
            }
            results.Add(BuildUnlockConditionRef(GetRecord(questIndex), questIndex, condition, ancestry));
        }
    }

    private SpecTreeRef BuildPrerequisiteRef(QuestResolutionRecord record, int questIndex, int prereqId) =>
        BuildPrerequisiteRef(record, questIndex, prereqId, Array.Empty<int>());


    private SpecTreeRef BuildPrerequisiteRef(QuestResolutionRecord record, int questIndex, int prereqId, int[] ancestry)

    {
        string name = _guide.GetDisplayName(prereqId);
        int prereqQuestIndex = _guide.FindQuestIndex(prereqId);
        bool done =
            IsQuestCompleted(questIndex)
                        || (prereqQuestIndex >= 0 && IsQuestCompleted(prereqQuestIndex));
        return SpecTreeRef.ForGraphNode(
            prereqId,
            SpecTreeKind.Prerequisite,
            questIndex,
            name,
            $"Requires: {name}",
            done,
            false,
            ancestry: AppendAncestry(ancestry, prereqId)
        );
    }

    private SpecTreeRef BuildGiverRef(QuestResolutionRecord record, int questIndex, int giverId) =>
        BuildGiverRef(record, questIndex, giverId, Array.Empty<int>());


    private SpecTreeRef BuildGiverRef(
        QuestResolutionRecord record,
        int questIndex,
        int giverId,
        int[] ancestry
    )
    {
        string name = _guide.GetDisplayName(giverId);
        FindGiverInteraction(questIndex, giverId, out _, out string? keyword);
        int? blockedByNodeId = SpecTreeRecordState.FindBlockingZoneLineNodeId(
            record,
            _guide.GetScene(giverId)
        );
        bool isBlocked =
            SpecTreeRecordState.GetBlockingRequirementGroups(_guide, _phases, _questTracker, giverId).Count > 0
            || blockedByNodeId.HasValue;
        bool isCompleted =
            _phases.GetPhase(questIndex) is QuestPhase.Accepted or QuestPhase.Completed;
        return SpecTreeRef.ForGraphNode(
            giverId,
            SpecTreeKind.Giver,
            questIndex,
            name,
            FormatAssignmentLabel(giverId, name, keyword),
            isCompleted,
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, giverId)
        );
    }

    private SpecTreeRef BuildRequiredItemRef(int questIndex, ItemReq requirement) =>
        BuildItemRequirementRef(
            GetRecord(questIndex),
            questIndex,
            requirement.ItemId,
            requirement.Quantity,
            Array.Empty<int>()
        );

    private SpecTreeRef BuildItemRequirementRef(
        QuestResolutionRecord record,
        int questIndex,
        int itemId,
        int quantity,
        int[] ancestry
    )

    {
        string name = _guide.GetDisplayName(itemId);
        int itemIndex = _guide.FindItemIndex(itemId);
        int have = itemIndex >= 0 ? _phases.GetItemCount(itemIndex) : 0;
        string label = quantity > 1 ? $"Collect: {name} ({have}/{quantity})" : $"Collect: {name}";
        return SpecTreeRef.ForGraphNode(
            itemId,
            SpecTreeKind.Item,
            questIndex,
            name,
            label,
            IsQuestCompleted(questIndex) || have >= quantity,
            false,
            ancestry: AppendAncestry(ancestry, itemId)
        );
    }

    private SpecTreeRef BuildStepRef(int questIndex, StepEntry step) =>
        BuildStepRef(GetRecord(questIndex), questIndex, step, Array.Empty<int>());

    private SpecTreeRef BuildStepRef(
        QuestResolutionRecord record,
        int questIndex,
        StepEntry step,
        int[] ancestry
    )
    {
        string name = _guide.GetDisplayName(step.TargetId);
        int? blockedByNodeId = SpecTreeRecordState.FindBlockingZoneLineNodeId(
            record,
            _guide.GetScene(step.TargetId)
        );
        bool isBlocked =
            SpecTreeRecordState.GetBlockingRequirementGroups(_guide, _phases, _questTracker, step.TargetId).Count > 0
            || blockedByNodeId.HasValue;
        return SpecTreeRef.ForGraphNode(
            step.TargetId,
            SpecTreeKind.Step,
            questIndex,
            name,
            FormatStepLabel(step, name),
            IsQuestCompleted(questIndex),
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, step.TargetId)
        );
    }

    private SpecTreeRef BuildCompleterRef(int questIndex, int completerId) =>
        BuildCompleterRef(GetRecord(questIndex), questIndex, completerId, Array.Empty<int>());

    private SpecTreeRef BuildCompleterRef(
        QuestResolutionRecord record,
        int questIndex,
        int completerId,
        int[] ancestry
    )
    {
        string name = _guide.GetDisplayName(completerId);
        FindCompletionInteraction(
            questIndex,
            completerId,
            out byte interactionType,
            out string? keyword
        );
        int? blockedByNodeId = SpecTreeRecordState.FindBlockingZoneLineNodeId(
            record,
            _guide.GetScene(completerId)
        );
        bool isBlocked =
            SpecTreeRecordState.GetBlockingRequirementGroups(_guide, _phases, _questTracker, completerId).Count > 0
            || blockedByNodeId.HasValue;
        return SpecTreeRef.ForGraphNode(
            completerId,
            SpecTreeKind.Completer,
            questIndex,
            name,
            FormatCompletionLabel(questIndex, completerId, name, interactionType, keyword),
            IsQuestCompleted(questIndex),
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, completerId)
        );
    }

    private SpecTreeRef BuildSourceRef(int questIndex, SourceSiteEntry source) =>
        BuildSourceRef(GetRecord(questIndex), questIndex, source, Array.Empty<int>());

    private SpecTreeRef BuildSourceRef(
        QuestResolutionRecord record,
        int questIndex,
        SourceSiteEntry source,
        int[] ancestry
    )
    {
        string name = _guide.GetDisplayName(source.SourceId);
        int? blockedByNodeId = SpecTreeRecordState.FindBlockingZoneLineNodeId(
            record,
            _guide.GetSourceScene(source)
        );
        bool isBlocked =
            SpecTreeRecordState.GetBlockingRequirementGroups(_guide, _phases, _questTracker, source.SourceId).Count > 0
            || blockedByNodeId.HasValue;
        bool isCompleted = IsQuestCompleted(questIndex) || IsQuestNodeCompleted(source.SourceId);
        return SpecTreeRef.ForGraphNode(
            source.SourceId,
            SpecTreeKind.Source,
            questIndex,
            name,
            FormatSourceLabel(source, name),
            isCompleted,
            isBlocked,
            blockedByNodeId,
            AppendAncestry(ancestry, source.SourceId),
            requiresVisibleChildren: source.SourceType == (byte)NodeType.Recipe
        );
    }

    private SpecTreeRef BuildRewardQuestSourceRef(
        QuestResolutionRecord record,
        int questIndex,
        int rewardQuestId,
        int[] ancestry
    )
    {
        string name = _guide.GetDisplayName(rewardQuestId);
        bool isCompleted = IsQuestCompleted(questIndex) || IsQuestNodeCompleted(rewardQuestId);
        return SpecTreeRef.ForGraphNode(
            rewardQuestId,
            SpecTreeKind.Source,
            questIndex,
            name,
            $"Complete {name}",
            isCompleted,
            false,
            ancestry: AppendAncestry(ancestry, rewardQuestId),
            requiresVisibleChildren: true
        );
    }

    private SpecTreeRef BuildUnlockConditionRef(int questIndex, UnlockConditionEntry condition) =>
        BuildUnlockConditionRef(GetRecord(questIndex), questIndex, condition, Array.Empty<int>());

    private SpecTreeRef BuildUnlockConditionRef(
        QuestResolutionRecord record,
        int questIndex,
        UnlockConditionEntry condition,
        int[] ancestry
    )
    {
        string name = _guide.GetDisplayName(condition.SourceId);
        SpecTreeKind kind = DetermineUnlockKind(condition);
        return SpecTreeRef.ForGraphNode(
            condition.SourceId,
            kind,
            questIndex,
            name,
            $"Requires: {name}",
            IsQuestCompleted(questIndex) || IsUnlockConditionSatisfied(condition),
            false,
            ancestry: AppendAncestry(ancestry, condition.SourceId),
            requiresVisibleChildren: kind == SpecTreeKind.Item
                && ItemHasPotentialChildren(condition.SourceId)
        );
    }

    private List<SourceSiteEntry> ApplyHostileDropFilter(ReadOnlySpan<SourceSiteEntry> sources)
    {
        var visible = new List<SourceSiteEntry>(sources.Length);
        ItemSourceVisibilityPolicy.Filter(sources, _guide, visible);
        return visible;
    }



    private static int? FindBlockingZoneLineNodeId(
        QuestResolutionRecord record,
        string? targetScene
    ) => SpecTreeRecordState.FindBlockingZoneLineNodeId(record, targetScene);

    private SpecTreeKind DetermineUnlockKind(UnlockConditionEntry condition)
    {
        if (condition.CheckType == 1)
            return SpecTreeKind.Item;

        return _guide.GetNode(condition.SourceId).Type == NodeType.Quest
            ? SpecTreeKind.Prerequisite
            : SpecTreeKind.Source;
    }

    private bool IsUnlockConditionSatisfied(UnlockConditionEntry condition) =>
        SpecTreeRecordState.IsUnlockConditionSatisfied(_guide, _phases, _questTracker, condition);

    private bool IsQuestNodeCompleted(int nodeId) =>
        SpecTreeRecordState.IsQuestNodeCompleted(_guide, _phases, nodeId);

    private bool IsQuestCompleted(int questIndex) => _phases.IsCompleted(questIndex);

    private int FindQuestIndex(string questKey)
    {
        if (!_guide.TryGetNodeId(questKey, out int questNodeId))
            throw new InvalidOperationException($"Compiled guide does not contain quest '{questKey}'.");
        int questIndex = _guide.FindQuestIndex(questNodeId);
        if (questIndex < 0)
            throw new InvalidOperationException($"Node '{questKey}' is not a quest.");
        return questIndex;
    }


    private IReadOnlyList<SpecTreeRef> GetQuestChildren(
        QuestResolutionRecord record,
        int questIndex,
        int[] ancestry
    )
    {
        var results = new List<SpecTreeRef>();
        foreach (int prereqId in _guide.PrereqQuestIds(questIndex))
            AddIfVisible(results, BuildPrerequisiteRef(record, questIndex, prereqId, ancestry));
        foreach (int giverId in _guide.GiverIds(questIndex))
            AddIfVisible(results, BuildGiverRef(record, questIndex, giverId, ancestry));
        foreach (var requirement in _guide.RequiredItems(questIndex))
            AddIfVisible(
                results,
                BuildItemRequirementRef(
                    record,
                    questIndex,
                    requirement.ItemId,
                    requirement.Quantity,
                    ancestry
                )
            );
        foreach (var step in _guide.Steps(questIndex))
            AddIfVisible(results, BuildStepRef(record, questIndex, step, ancestry));
        foreach (int completerId in _guide.CompleterIds(questIndex))
            AddIfVisible(results, BuildCompleterRef(record, questIndex, completerId, ancestry));
        return results;
    }

    private IReadOnlyList<SpecTreeRef> GetRecipeMaterialChildren(
        QuestResolutionRecord record,
        int questIndex,
        int recipeNodeId,
        int[] ancestry
    )
    {
        var results = new List<SpecTreeRef>();
        foreach (
            var materialEdge in _guide.OutEdges(
                _guide.GetNodeKey(recipeNodeId),
                EdgeType.RequiresMaterial
            )
        )
        {
            if (!_guide.TryGetNodeId(materialEdge.Target, out int materialId))
                continue;
            AddIfVisible(
                results,
                BuildItemRequirementRef(
                    record,
                    questIndex,
                    materialId,
                    materialEdge.Quantity ?? 1,
                    ancestry
                )
            );
        }
        return results;
    }

    private void AddIfVisible(List<SpecTreeRef> results, SpecTreeRef candidate)
    {
        if (!IsMeaningfullyVisible(candidate))
        {
            _lastPrunedCount++;
            return;
        }
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
        string cacheKey = BuildProjectionKey("visible", candidate);
        if (_visibilityCache.TryGetValue(cacheKey, out bool cachedVisible))
            return cachedVisible;
        if (!_activeProjectionKeys.Add(cacheKey))
        {
            _lastCyclePruneCount++;
            return false;
        }

        try
        {
            bool requiresVisibleChildren = RequiresVisibleChildren(candidate);
            bool selfVisible =
                candidate.IsCompleted || (!requiresVisibleChildren && !candidate.IsBlocked);
            if (selfVisible)
            {
                _visibilityCache[cacheKey] = true;
                return true;
            }

            bool hasVisibleDescendants =
                GetUnlockChildrenCore(candidate).Count > 0 || GetChildrenCore(candidate).Count > 0;
            _visibilityCache[cacheKey] = hasVisibleDescendants;
            return hasVisibleDescendants;
        }
        finally
        {
            _activeProjectionKeys.Remove(cacheKey);
        }
    }

    private bool RequiresVisibleChildren(SpecTreeRef candidate)
    {
        if (candidate.RequiresVisibleChildren)
            return true;
        if (candidate.Kind == SpecTreeKind.Source)
        {
            if (candidate.GraphNodeId is not int graphNodeId)
                return false;
            var node = _guide.GetNode(graphNodeId);
            return node?.Type is NodeType.Quest or NodeType.Recipe;
        }
        return false;
    }

    private bool HasAncestryCycle(SpecTreeRef candidate)
    {
        if (candidate.GraphNodeId is not int graphNodeId || candidate.Ancestry.Length < 2)
            return false;
        for (int i = 0; i < candidate.Ancestry.Length - 1; i++)
        {
            if (candidate.Ancestry[i] == graphNodeId)
            {
                _lastCyclePruneCount++;
                return true;
            }
        }
        return false;
    }

    internal void ResetProjectionCaches(int invalidatedQuestCount = 0, bool full = true)
    {
        _childCache.Clear();
        _unlockCache.Clear();
        _visibilityCache.Clear();
        _activeProjectionKeys.Clear();
        _lastInvalidatedQuestCount = invalidatedQuestCount;
        _lastInvalidationWasFull = full;
    }

    private void EnterProjection()
    {
        if (_projectionDepth == 0)
            _activeProjectionKeys.Clear();

        _projectionDepth++;
    }

    private void ExitProjection()
    {
        if (_projectionDepth > 0)
            _projectionDepth--;
    }

    private static string BuildProjectionKey(string scope, SpecTreeRef candidate)
    {
        return string.Join(
            "|",
            new object?[]
            {
                scope,
                candidate.Kind,
                candidate.QuestIndex,
                candidate.StableId,
                candidate.GraphNodeId,
                candidate.BlockedByGraphNodeId,
                candidate.IsCompleted,
                candidate.IsBlocked,
                candidate.RequiresVisibleChildren,
                candidate.Label,
                candidate.DisplayName,
                candidate.SyntheticChildren?.Length,
                candidate.Ancestry.Length,
                candidate.Ancestry.Length > 0 ? candidate.Ancestry[^1] : null,
                candidate.Ancestry.Length > 1 ? candidate.Ancestry[^2] : null,
                candidate.Ancestry.Length > 2 ? candidate.Ancestry[^3] : null,
            }
        );
    }

    private SpecTreeRef[] BuildUnlockGroupChildren(
        QuestResolutionRecord record,
        int questIndex,
        int[] ancestry,
        IReadOnlyList<UnlockConditionEntry> conditions
    )
    {
        var children = new List<SpecTreeRef>();
        for (int i = 0; i < conditions.Count; i++)
        {
            if (ancestry.Contains(conditions[i].SourceId))
            {
                _lastCyclePruneCount++;
                continue;
            }
            children.Add(BuildUnlockConditionRef(record, questIndex, conditions[i], ancestry));
        }
        return children.ToArray();
    }

    private SpecTreeRef BuildGroupRef(
        QuestResolutionRecord record,
        int questIndex,
        string label,
        int[] ancestry,
        SpecTreeRef[] children
    )
    {
        string stableId = string.Join(
            "|",
            "group",
            questIndex.ToString(),
            label,
            string.Join(",", ancestry),
            string.Join(",", children.Select(child => child.StableId))
        );
        return SpecTreeRef.ForSynthetic(
            stableId,
            SpecTreeKind.Group,
            questIndex,
            label,
            label,
            IsQuestCompleted(questIndex),
            false,
            ancestry: ancestry,
            syntheticChildren: children,
            requiresVisibleChildren: true
        );
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

    private string FormatCompletionLabel(
        int questIndex,
        int nodeId,
        string name,
        byte interactionType,
        string? keyword
    )
    {
        var node = _guide.GetNode(nodeId);
        if (node == null)
            return $"Complete via: {name}";

        return node.Type switch
        {
            NodeType.Character => FormatCharacterCompletionLabel(
                questIndex,
                name,
                interactionType,
                keyword
            ),
            NodeType.Item => $"Read {name}",
            NodeType.Zone => $"Enter {name}",
            NodeType.ZoneLine => $"Travel to {name}",
            NodeType.Quest => $"Complete {name}",
            _ => $"Complete via: {name}",
        };
    }

    private string FormatCharacterCompletionLabel(
        int questIndex,
        string name,
        byte interactionType,
        string? keyword
    )
    {
        if (QuestCompletionSemantics.UsesKeywordInteraction(interactionType, keyword))
            return FormatKeywordLabel("Talk to ", name, keyword);

        int questNodeId = _guide.QuestNodeId(questIndex);
        var questNode = _guide.GetNode(questNodeId);
        return questNode != null && QuestCompletionSemantics.HasTurnInPayload(_guide, questNode)
            ? $"Turn in to {name}"
            : $"Talk to {name}";
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

    private static List<IReadOnlyList<UnlockConditionEntry>> DeduplicateUnlockGroups(
        IReadOnlyList<IReadOnlyList<UnlockConditionEntry>> groups
    )
    {
        var deduped = new List<IReadOnlyList<UnlockConditionEntry>>(groups.Count);
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var group in groups)
        {
            string key = BuildUnlockGroupKey(group);
            if (seen.Add(key))
                deduped.Add(group);
        }

        return deduped;
    }

    private static string BuildUnlockGroupKey(IReadOnlyList<UnlockConditionEntry> group)
    {
        return string.Join(
            "|",
            group
                .Select(condition => $"{condition.SourceId}:{condition.CheckType}")
                .OrderBy(value => value, StringComparer.Ordinal)
        );
    }

    private void FindGiverInteraction(
        int questIndex,
        int giverId,
        out byte interactionType,
        out string? keyword
    )
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

    private void FindCompletionInteraction(
        int questIndex,
        int completerId,
        out byte interactionType,
        out string? keyword
    )
    {
        int questNodeId = _guide.QuestNodeId(questIndex);
        foreach (var blueprint in _guide.CompletionBlueprints)
        {
            if (blueprint.QuestId == questNodeId && blueprint.CharacterId == completerId)
            {
                interactionType = blueprint.InteractionType;
                keyword = blueprint.Keyword;
                return;
            }
        }

        interactionType = 0;
        keyword = null;
    }

    internal SpecTreeDiagnosticsSnapshot ExportDiagnosticsSnapshot()
    {
        return new SpecTreeDiagnosticsSnapshot(
            lastProjectedNodeCount: _lastProjectedNodeCount,
            lastChildCount: _lastChildCount,
            lastPrunedCount: _lastPrunedCount,
            lastCyclePruneCount: _lastCyclePruneCount,
            lastInvalidatedQuestCount: _lastInvalidatedQuestCount,
            lastInvalidationWasFull: _lastInvalidationWasFull
        );
    }
}
