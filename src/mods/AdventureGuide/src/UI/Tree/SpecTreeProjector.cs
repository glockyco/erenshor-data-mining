using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;

namespace AdventureGuide.UI.Tree;

public sealed class SpecTreeProjector
{
    private const byte EdgeDropsItem = 16;
    private const byte EdgeSellsItem = 17;
    private const byte EdgeGivesItem = 18;
    private const byte EdgeContains = 29;
    private const byte EdgeYieldsItem = 31;
    private const byte EdgeProduces = 21;

    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly QuestPhaseTracker _phases;
    private readonly UnlockPredicateEvaluator _unlocks;

    public SpecTreeProjector(
        CompiledGuide.CompiledGuide guide,
        QuestPhaseTracker phases,
        UnlockPredicateEvaluator unlocks)
    {
        _guide = guide;
        _phases = phases;
        _unlocks = unlocks;
    }

    public IReadOnlyList<SpecTreeRef> GetRootChildren(int questIndex)
    {
        var results = new List<SpecTreeRef>();

        foreach (int prereqId in _guide.PrereqQuestIds(questIndex))
            results.Add(BuildPrerequisiteRef(questIndex, prereqId));

        foreach (int giverId in _guide.GiverIds(questIndex))
            results.Add(BuildGiverRef(questIndex, giverId));

        foreach (var requirement in _guide.RequiredItems(questIndex))
            results.Add(BuildRequiredItemRef(questIndex, requirement));

        foreach (var step in _guide.Steps(questIndex))
            results.Add(BuildStepRef(questIndex, step));

        foreach (int completerId in _guide.CompleterIds(questIndex))
            results.Add(BuildCompleterRef(questIndex, completerId));

        return results;
    }

    public IReadOnlyList<SpecTreeRef> GetChildren(SpecTreeRef parent)
    {
        if (parent.Kind == SpecTreeKind.Prerequisite)
        {
            int prereqQuestIndex = _guide.FindQuestIndex(parent.NodeId);
            return prereqQuestIndex >= 0
                ? GetRootChildren(prereqQuestIndex)
                : Array.Empty<SpecTreeRef>();
        }

        if (parent.Kind != SpecTreeKind.Item)
            return Array.Empty<SpecTreeRef>();

        int itemIndex = _guide.FindItemIndex(parent.NodeId);
        if (itemIndex < 0)
            return Array.Empty<SpecTreeRef>();

        var sources = _guide.GetItemSources(itemIndex);
        if (sources.Length == 0)
            return Array.Empty<SpecTreeRef>();

        var visibleSources = ApplyHostileDropFilter(sources);
        var results = new List<SpecTreeRef>(visibleSources.Count);
        for (int i = 0; i < visibleSources.Count; i++)
            results.Add(BuildSourceRef(parent.QuestIndex, visibleSources[i]));
        return results;
    }

    public IReadOnlyList<SpecTreeRef> GetUnlockChildren(SpecTreeRef parent)
    {
        if (!_guide.TryGetUnlockPredicate(parent.NodeId, out var predicate))
            return Array.Empty<SpecTreeRef>();

        var results = new List<SpecTreeRef>(predicate.Conditions.Length);
        foreach (var condition in predicate.Conditions)
            results.Add(BuildUnlockConditionRef(parent.QuestIndex, condition));
        return results;
    }

    private SpecTreeRef BuildPrerequisiteRef(int questIndex, int prereqId)
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
            false);
    }

    private SpecTreeRef BuildGiverRef(int questIndex, int giverId)
    {
        string name = _guide.GetDisplayName(giverId);
        FindGiverInteraction(questIndex, giverId, out _, out string? keyword);
        return new SpecTreeRef(
            giverId,
            SpecTreeKind.Giver,
            questIndex,
            name,
            FormatAssignmentLabel(giverId, name, keyword),
            false,
            _unlocks.Evaluate(giverId) == UnlockResult.Blocked);
    }

    private SpecTreeRef BuildRequiredItemRef(int questIndex, ItemReq requirement)
    {
        string name = _guide.GetDisplayName(requirement.ItemId);
        int itemIndex = _guide.FindItemIndex(requirement.ItemId);
        int have = itemIndex >= 0 ? _phases.GetItemCount(itemIndex) : 0;
        string label = requirement.Quantity > 1
            ? $"Collect: {name} ({have}/{requirement.Quantity})"
            : $"Collect: {name}";
        return new SpecTreeRef(
            requirement.ItemId,
            SpecTreeKind.Item,
            questIndex,
            name,
            label,
            have >= requirement.Quantity,
            false);
    }

    private SpecTreeRef BuildStepRef(int questIndex, StepEntry step)
    {
        string name = _guide.GetDisplayName(step.TargetId);
        return new SpecTreeRef(
            step.TargetId,
            SpecTreeKind.Step,
            questIndex,
            name,
            FormatStepLabel(step, name),
            false,
            _unlocks.Evaluate(step.TargetId) == UnlockResult.Blocked);
    }

    private SpecTreeRef BuildCompleterRef(int questIndex, int completerId)
    {
        string name = _guide.GetDisplayName(completerId);
        FindCompletionInteraction(questIndex, completerId, out _, out string? keyword);
        return new SpecTreeRef(
            completerId,
            SpecTreeKind.Completer,
            questIndex,
            name,
            FormatCompletionLabel(completerId, name, keyword),
            false,
            _unlocks.Evaluate(completerId) == UnlockResult.Blocked);
    }

    private SpecTreeRef BuildSourceRef(int questIndex, SourceSiteEntry source)
    {
        string name = _guide.GetDisplayName(source.SourceId);
        return new SpecTreeRef(
            source.SourceId,
            SpecTreeKind.Source,
            questIndex,
            name,
            FormatSourceLabel(source, name),
            false,
            _unlocks.Evaluate(source.SourceId) == UnlockResult.Blocked);
    }

    private SpecTreeRef BuildUnlockConditionRef(int questIndex, UnlockConditionEntry condition)
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
            false);
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
            EdgeDropsItem  => $"Drops from: {name}",
            EdgeSellsItem  => $"Vendor: {name}",
            EdgeGivesItem  => FormatKeywordLabel("Talk to ", name, source.Keyword),
            EdgeContains   => $"Collect from: {name}",
            EdgeProduces   => $"Crafted via: {name}",
            EdgeYieldsItem => FormatYieldLabel(source, name),
            _              => name,
        };
    }

    private string FormatYieldLabel(SourceSiteEntry source, string name)
    {
    return source.SourceType switch
    {
        6 => $"Mine at: {name}",
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
