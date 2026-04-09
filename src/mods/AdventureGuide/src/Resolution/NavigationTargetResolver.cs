using AdventureGuide.Graph;
using AdventureGuide.Plan;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution;

/// <summary>
/// Resolves navigation targets for compiled-guide quest keys.
/// Non-quest keys are intentionally unsupported after the clean-cut runtime migration.
/// </summary>
public sealed class NavigationTargetResolver
{
	private readonly CompiledGuideModel _guide;
	private readonly EffectiveFrontier _frontier;
	private readonly SourceResolver _sourceResolver;
	private readonly Func<int> _versionProvider;

	public int Version => _versionProvider();

	public NavigationTargetResolver(
		CompiledGuideModel guide,
		EffectiveFrontier frontier,
		SourceResolver sourceResolver,
		Func<int>? versionProvider = null)
	{
		_guide = guide;
		_frontier = frontier;
		_sourceResolver = sourceResolver;
		_versionProvider = versionProvider ?? (() => 0);
	}

	public IReadOnlyList<ResolvedQuestTarget> Resolve(string nodeKey, string currentScene)
	{
		if (string.IsNullOrWhiteSpace(nodeKey))
			return Array.Empty<ResolvedQuestTarget>();

				if (_guide.TryGetNodeId(nodeKey, out int nodeId)
			&& _guide.GetNode(nodeId).Type == NodeType.Quest)
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
		var node = _guide.GetNode(nodeKey) ?? BuildNodeFromGuide(nodeKey);
		return new ResolvedNodeContext(nodeKey, node);
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
