using AdventureGuide.Graph;
using AdventureGuide.Position;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution;

/// <summary>
/// Projects compiled quest targets into navigation targets without owning cache
/// state. QuestResolutionService stores the projected result in each shared
/// resolution record.
/// </summary>
public sealed class QuestTargetProjector
{
    private readonly CompiledGuideModel _guide;
    private readonly ZoneRouter? _zoneRouter;

    public QuestTargetProjector(CompiledGuideModel guide, ZoneRouter? zoneRouter)
    {
        _guide = guide;
        _zoneRouter = zoneRouter;
    }

    public IReadOnlyList<ResolvedQuestTarget> Project(
        IReadOnlyList<ResolvedTarget> compiledTargets,
        string currentScene
    )
    {
        if (compiledTargets.Count == 0)
            return Array.Empty<ResolvedQuestTarget>();

        var results = new List<ResolvedQuestTarget>(compiledTargets.Count);
        for (int i = 0; i < compiledTargets.Count; i++)
            results.Add(Project(compiledTargets[i], currentScene));
        return results;
    }

    internal ResolvedNodeContext BuildNodeContext(int nodeId) =>
        BuildNodeContext(_guide.GetNodeKey(nodeId));

    internal ResolvedNodeContext BuildNodeContext(string nodeKey)
    {
        var node = _guide.GetNode(nodeKey) ?? BuildNodeFromGuide(nodeKey);
        return new ResolvedNodeContext(nodeKey, node);
    }

    internal bool IsSceneBlocked(string currentScene, string? targetScene)
    {
        if (_zoneRouter == null)
            return false;
        if (string.IsNullOrWhiteSpace(currentScene) || string.IsNullOrWhiteSpace(targetScene))
            return false;
        if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
            return false;
        return _zoneRouter.FindFirstLockedHop(currentScene, targetScene) != null;
    }

    private ResolvedQuestTarget Project(ResolvedTarget target, string currentScene)
    {
        string targetNodeKey = _guide.GetNodeKey(target.TargetNodeId);
        string sourceKey = _guide.GetNodeKey(target.PositionNodeId);
        var goalNode = BuildGoalContext(target);
        var targetNode = BuildNodeContext(target.TargetNodeId);
        var explanation = target.Semantic.ActionKind == ResolvedActionKind.LootChest
            ? NavigationExplanationBuilder.BuildLootChestExplanation(
                target.Semantic,
                goalNode,
                targetNode
            )
            : NavigationExplanationBuilder.Build(target.Semantic, goalNode, targetNode);

        string? requiredForQuestKey = null;
        if (target.RequiredForQuestIndex >= 0)
            requiredForQuestKey = _guide.GetNodeKey(_guide.QuestNodeId(target.QuestIndex));

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
            requiredForQuestKey: requiredForQuestKey,
            isBlockedPath: IsSceneBlocked(currentScene, target.Scene),
            availabilityPriority: target.AvailabilityPriority
        );
    }

    private ResolvedNodeContext BuildGoalContext(ResolvedTarget target)
    {
        if (!string.IsNullOrEmpty(target.Semantic.GoalNodeKey))
            return BuildNodeContext(target.Semantic.GoalNodeKey);

        return BuildNodeContext(target.TargetNodeId);
    }

    private Node BuildNodeFromGuide(string nodeKey)
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
            Type = record.Type,
            DisplayName = _guide.GetDisplayName(nodeId),
            Scene = _guide.GetScene(nodeId),
            X = record.X,
            Y = record.Y,
            Z = record.Z,
            DbName = record.DbName,
            Repeatable = record.Repeatable,
            Implicit = record.Implicit,
            Disabled = record.Disabled,
            IsEnabled = record.IsEnabled,
        };
    }
}
