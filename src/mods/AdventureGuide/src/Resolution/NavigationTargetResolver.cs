using AdventureGuide.Graph;
using AdventureGuide.Plan;

namespace AdventureGuide.Resolution;

/// <summary>
/// Resolves navigation targets for compiled-guide quest keys.
/// Non-quest keys are intentionally unsupported after the clean-cut runtime migration.
/// </summary>
public sealed class NavigationTargetResolver
{
    private readonly CompiledGuide.CompiledGuide _guide;
    private readonly EntityGraph _graph;
    private readonly EffectiveFrontier _frontier;
    private readonly SourceResolver _sourceResolver;
    private readonly Func<int> _versionProvider;

    public int Version => _versionProvider();

    public NavigationTargetResolver(
        CompiledGuide.CompiledGuide guide,
        EntityGraph graph,
        EffectiveFrontier frontier,
        SourceResolver sourceResolver,
        Func<int>? versionProvider = null)
    {
        _guide = guide;
        _graph = graph;
        _frontier = frontier;
        _sourceResolver = sourceResolver;
        _versionProvider = versionProvider ?? (() => 0);
    }

    public IReadOnlyList<ResolvedQuestTarget> Resolve(string nodeKey, string currentScene)
    {
        if (string.IsNullOrWhiteSpace(nodeKey))
            return Array.Empty<ResolvedQuestTarget>();

        if (_guide.TryGetNodeId(nodeKey, out int nodeId)
            && _guide.GetNode(nodeId).NodeType == (byte)NodeType.Quest)
        {
            int questIndex = FindQuestIndex(nodeId);
            if (questIndex < 0)
                return Array.Empty<ResolvedQuestTarget>();

            return ResolveQuestTargets(questIndex, currentScene);
        }
        return Array.Empty<ResolvedQuestTarget>();
    }

    private IReadOnlyList<ResolvedQuestTarget> ResolveQuestTargets(int questIndex, string currentScene)
    {
        var frontier = new List<FrontierEntry>();
        _frontier.Resolve(questIndex, frontier, -1);

        var results = new List<ResolvedQuestTarget>();
        for (int i = 0; i < frontier.Count; i++)
        {
            var compiledTargets = _sourceResolver.ResolveTargets(frontier[i], currentScene);
            for (int j = 0; j < compiledTargets.Count; j++)
                results.Add(ConvertCompiledTarget(compiledTargets[j]));
        }

        return results;
    }

    private ResolvedQuestTarget ConvertCompiledTarget(ResolvedTarget target)
    {
        string targetNodeKey = _guide.GetNodeKey(target.TargetNodeId);
        string sourceKey = _guide.GetNodeKey(target.PositionNodeId);
        var goalNode = BuildGoalContext(target);
        var targetNode = BuildNodeContext(target.TargetNodeId);
        var explanation = target.Semantic.ActionKind == ResolvedActionKind.LootChest
            ? NavigationExplanationBuilder.BuildLootChestExplanation(target.Semantic, goalNode, targetNode)
            : NavigationExplanationBuilder.Build(target.Semantic, goalNode, targetNode);

        string? requiredForQuestKey = null;
        if (target.RequiredForQuestIndex >= 0)
            requiredForQuestKey = _guide.GetNodeKey(_guide.QuestNodeId(target.RequiredForQuestIndex));

        return new ResolvedQuestTarget(
            targetNodeKey,
            target.Scene,
            sourceKey,
            goalNode,
            targetNode,
            target.Semantic,
            explanation,
            target.X,
            target.Y,
            target.Z,
            target.IsActionable,
            requiredForQuestKey: requiredForQuestKey);
    }

    private ResolvedNodeContext BuildGoalContext(ResolvedTarget target)
    {
        if (!string.IsNullOrEmpty(target.Semantic.GoalNodeKey))
            return BuildNodeContext(target.Semantic.GoalNodeKey);

        return BuildNodeContext(target.TargetNodeId);
    }

    private ResolvedNodeContext BuildNodeContext(int nodeId) =>
        BuildNodeContext(_guide.GetNodeKey(nodeId));

    private ResolvedNodeContext BuildNodeContext(string nodeKey)
    {
        var node = _graph.GetNode(nodeKey) ?? CreateSyntheticNode(nodeKey);
        return new ResolvedNodeContext(nodeKey, node);
    }

    private Node CreateSyntheticNode(string nodeKey)
    {
        if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
        {
            return new Node
            {
                Key = nodeKey,
                Type = NodeType.WorldObject,
                DisplayName = nodeKey,
            };
        }

        var record = _guide.GetNode(nodeId);
        return new Node
        {
            Key = nodeKey,
            Type = (NodeType)record.NodeType,
            DisplayName = _guide.GetDisplayName(nodeId),
            Scene = _guide.GetScene(nodeId),
            X = float.IsNaN(record.X) ? null : record.X,
            Y = float.IsNaN(record.Y) ? null : record.Y,
            Z = float.IsNaN(record.Z) ? null : record.Z,
            DbName = record.DbNameOffset == 0 ? null : _guide.GetString(record.DbNameOffset),
            Repeatable = (record.Flags & (ushort)AdventureGuide.CompiledGuide.NodeFlags.Repeatable) != 0,
            Implicit = (record.Flags & (ushort)AdventureGuide.CompiledGuide.NodeFlags.Implicit) != 0,
            Disabled = (record.Flags & (ushort)AdventureGuide.CompiledGuide.NodeFlags.Disabled) != 0,
            IsEnabled = (record.Flags & (ushort)AdventureGuide.CompiledGuide.NodeFlags.IsEnabled) != 0,
        };
    }

    private int FindQuestIndex(int questNodeId)
    {
        for (int questIndex = 0; questIndex < _guide.QuestCount; questIndex++)
        {
            if (_guide.QuestNodeId(questIndex) == questNodeId)
                return questIndex;
        }

        return -1;
    }
}
