using AdventureGuide.Graph;
using AdventureGuide.Position;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution;

public sealed class QuestTargetProjector
{
	public sealed class PrecomputedBlockingZoneMap
	{
		private readonly IReadOnlyDictionary<string, int> _blockingZoneLineByTargetScene;

		public PrecomputedBlockingZoneMap(
			string projectedScene,
			IReadOnlyDictionary<string, int> blockingZoneLineByTargetScene)
		{
			ProjectedScene = projectedScene;
			_blockingZoneLineByTargetScene = new Dictionary<string, int>(
				blockingZoneLineByTargetScene,
				StringComparer.OrdinalIgnoreCase);
		}

		public string ProjectedScene { get; }

		public bool MatchesScene(string currentScene) =>
			string.Equals(ProjectedScene, currentScene, StringComparison.OrdinalIgnoreCase);

		public bool TryGetBlockingZoneLineNodeId(string? targetScene, out int zoneLineNodeId)
		{
			zoneLineNodeId = default;
			return !string.IsNullOrWhiteSpace(targetScene)
				&& _blockingZoneLineByTargetScene.TryGetValue(targetScene, out zoneLineNodeId);
		}
	}

	private readonly CompiledGuideModel _guide;
	private readonly ZoneRouter? _zoneRouter;

	public QuestTargetProjector(CompiledGuideModel guide, ZoneRouter? zoneRouter)
	{
		_guide = guide;
		_zoneRouter = zoneRouter;
	}

	public IReadOnlyList<ResolvedQuestTarget> Project(
		IReadOnlyList<ResolvedTarget> compiledTargets,
		string currentScene,
		PrecomputedBlockingZoneMap? blockingZoneMap = null)
	{
		if (compiledTargets.Count == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var results = new List<ResolvedQuestTarget>(compiledTargets.Count);
		for (int i = 0; i < compiledTargets.Count; i++)
			results.Add(Project(compiledTargets[i], currentScene, blockingZoneMap));
		return results;
	}

	internal ResolvedNodeContext BuildNodeContext(int nodeId) =>
		BuildNodeContext(_guide.GetNodeKey(nodeId));

	internal ResolvedNodeContext BuildNodeContext(string nodeKey)
	{
		var node = _guide.GetNode(nodeKey) ?? BuildNodeFromGuide(nodeKey);
		return new ResolvedNodeContext(nodeKey, node);
	}

	internal bool IsSceneBlocked(
		string currentScene,
		string? targetScene,
		PrecomputedBlockingZoneMap? blockingZoneMap = null)
	{
		if (string.IsNullOrWhiteSpace(currentScene) || string.IsNullOrWhiteSpace(targetScene))
			return false;
		if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
			return false;
		if (blockingZoneMap != null && blockingZoneMap.MatchesScene(currentScene))
			return blockingZoneMap.TryGetBlockingZoneLineNodeId(targetScene, out _);
		if (_zoneRouter == null)
			return false;
		return _zoneRouter.FindFirstLockedHop(currentScene, targetScene) != null;
	}

	private ResolvedQuestTarget Project(
		ResolvedTarget target,
		string currentScene,
		PrecomputedBlockingZoneMap? blockingZoneMap)
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
			isBlockedPath: IsSceneBlocked(currentScene, target.Scene, blockingZoneMap),
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
