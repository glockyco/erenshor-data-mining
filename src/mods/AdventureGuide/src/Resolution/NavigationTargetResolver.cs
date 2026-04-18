using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Position;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution;

/// <summary>
/// Resolves navigation targets for compiled-guide node keys.
/// Quest keys use canonical quest-target resolution; non-quest entity keys
/// resolve positions directly from the compiled guide.
/// </summary>
public sealed class NavigationTargetResolver
{
	private readonly CompiledGuideModel _guide;
	private readonly QuestResolutionService _questResolutionService;
	private readonly ZoneRouter? _zoneRouter;
	private readonly PositionResolverRegistry _positionResolvers;
	private readonly DiagnosticsCore? _diagnostics;
	private readonly Dictionary<string, IReadOnlyList<ResolvedQuestTarget>> _questTargetCache = new(	    StringComparer.Ordinal
	);
	private int _cachedQuestTargetVersion = -1;
	private string? _lastResolvedNodeKey;
	private int _lastResolvedTargetCount;
	private int _lastBatchKeyCount;
	private IReadOnlyList<QuestCostSample> _topQuestCosts = Array.Empty<QuestCostSample>();
	public int Version => _questResolutionService.Version;	internal NavigationTargetResolver(
	    CompiledGuideModel guide,
	    QuestResolutionService questResolutionService,
	    ZoneRouter? zoneRouter,
	    PositionResolverRegistry positionResolvers,
	    DiagnosticsCore? diagnostics = null
	)
	{
	    _guide = guide;
	    _questResolutionService = questResolutionService;
	    _zoneRouter = zoneRouter;
	    _positionResolvers = positionResolvers;
	    _diagnostics = diagnostics;
	}	public IReadOnlyList<ResolvedQuestTarget> Resolve(
		string nodeKey,
		string currentScene,
		IResolutionTracer? tracer = null
	)
	{
		var token = _diagnostics?.BeginSpan(
			DiagnosticSpanKind.NavResolverResolve,
			DiagnosticsContext.Root(DiagnosticTrigger.Unknown),
			primaryKey: nodeKey
		);
		long startTick = Stopwatch.GetTimestamp();
		try
		{
			tracer?.OnResolveBegin(nodeKey);

			if (string.IsNullOrWhiteSpace(nodeKey))
				return Array.Empty<ResolvedQuestTarget>();

			if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
				return Array.Empty<ResolvedQuestTarget>();

			if (_cachedQuestTargetVersion != Version)
			{
			    _questTargetCache.Clear();
			    _cachedQuestTargetVersion = Version;
			}

			var node = _guide.GetNode(nodeId);
			IReadOnlyList<ResolvedQuestTarget> results;
			if (node.Type == NodeType.Quest)
			{
			    string cacheKey = BuildQuestCacheKey(nodeKey, currentScene);
			    if (!_questTargetCache.TryGetValue(cacheKey, out results!))
			    {
			        results = ResolveQuestTargets(nodeId, currentScene, tracer);
			        _questTargetCache[cacheKey] = results;
			    }
			}
			else
			{
			    results = ResolveNonQuestEntity(nodeId, nodeKey, node, currentScene);
			}

			_lastResolvedNodeKey = nodeKey;
			_lastBatchKeyCount = 1;
			_topQuestCosts = Array.Empty<QuestCostSample>();
			_lastResolvedTargetCount = results.Count;			tracer?.OnResolveEnd(results.Count);
			return results;
		}
		finally
		{
			if (token != null)
				_diagnostics!.EndSpan(
					token.Value,
					Stopwatch.GetTimestamp() - startTick,
					value0: _lastResolvedTargetCount,
					value1: 0
				);
		}
	}

	private static string BuildQuestCacheKey(string nodeKey, string currentScene) =>
    nodeKey + "\n" + (currentScene ?? string.Empty).ToUpperInvariant();

internal IReadOnlyDictionary<string, IReadOnlyList<ResolvedQuestTarget>> ResolveBatch(
    IEnumerable<string> nodeKeys,
    string currentScene,
    IResolutionTracer? tracer = null
)
{
    if (_cachedQuestTargetVersion != Version)
    {
        _questTargetCache.Clear();
        _cachedQuestTargetVersion = Version;
    }

    var results = new Dictionary<string, IReadOnlyList<ResolvedQuestTarget>>(StringComparer.Ordinal);
    var questKeys = new List<string>();
    var seen = new HashSet<string>(StringComparer.Ordinal);
    foreach (var nodeKey in nodeKeys)
    {
        if (string.IsNullOrWhiteSpace(nodeKey) || !seen.Add(nodeKey))
            continue;
        if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
        {
            results[nodeKey] = Array.Empty<ResolvedQuestTarget>();
            continue;
        }

        var node = _guide.GetNode(nodeId);
        if (node.Type == NodeType.Quest)
        {
            questKeys.Add(nodeKey);
            continue;
        }

        results[nodeKey] = ResolveNonQuestEntity(nodeId, nodeKey, node, currentScene);
    }

    var records = _questResolutionService.ResolveBatch(questKeys, currentScene, tracer);
    _lastBatchKeyCount = seen.Count;
    _topQuestCosts = _questResolutionService.TopQuestCosts;
    int totalResolvedTargets = 0;
    for (int i = 0; i < questKeys.Count; i++)
    {
        string questKey = questKeys[i];
        string cacheKey = BuildQuestCacheKey(questKey, currentScene);
        if (!_questTargetCache.TryGetValue(cacheKey, out var questResults))
        {
            if (records.TryGetValue(questKey, out var record) && record.CompiledTargets.Count > 0)
            {
                var projected = new List<ResolvedQuestTarget>(record.CompiledTargets.Count);
                for (int j = 0; j < record.CompiledTargets.Count; j++)
                    projected.Add(ConvertCompiledTarget(record.CompiledTargets[j], currentScene));
                questResults = projected;
            }
            else
            {
                questResults = Array.Empty<ResolvedQuestTarget>();
            }
            _questTargetCache[cacheKey] = questResults;
        }

        results[questKey] = questResults;
        totalResolvedTargets += questResults.Count;
    }

    _lastResolvedTargetCount = totalResolvedTargets;
    return results;
}

	private IReadOnlyList<ResolvedQuestTarget> ResolveQuestTargets(
	    int questNodeId,
	    string currentScene,
	    IResolutionTracer? tracer
	)
	{
		int questIndex = _guide.FindQuestIndex(questNodeId);
		if (questIndex < 0)
			return Array.Empty<ResolvedQuestTarget>();

		string questKey = _guide.GetNodeKey(questNodeId);
		var compiledTargets = _questResolutionService.ResolveQuest(questKey, currentScene, tracer).CompiledTargets;
		if (compiledTargets.Count == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var results = new List<ResolvedQuestTarget>(compiledTargets.Count);
		for (int i = 0; i < compiledTargets.Count; i++)
			results.Add(ConvertCompiledTarget(compiledTargets[i], currentScene));
		return results;
	}

	internal NavigationDiagnosticsSnapshot ExportDiagnosticsSnapshot()
	{
		return new NavigationDiagnosticsSnapshot(
			lastForceReason: DiagnosticTrigger.Unknown,
			cacheEntryCount: _questTargetCache.Count,
			currentTargetKey: _lastResolvedNodeKey,
			lastResolvedTargetCount: _lastResolvedTargetCount,
			lastBatchKeyCount: _lastBatchKeyCount,
			lastBatchWasPartialRefresh: false,
			topQuestCosts: _topQuestCosts
		);
	}

	private ResolvedQuestTarget ConvertCompiledTarget(ResolvedTarget target, string currentScene)
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
		{
		    requiredForQuestKey = _guide.GetNodeKey(_guide.QuestNodeId(target.QuestIndex));
		}

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

	// ---------------------------------------------------------------
	// Non-quest entity resolution
	// ---------------------------------------------------------------

	private IReadOnlyList<ResolvedQuestTarget> ResolveNonQuestEntity(
		int nodeId,
		string nodeKey,
		Node node,
		string currentScene
	)
	{
		return node.Type switch
		{
			NodeType.Character => ResolveCharacterTargets(nodeKey, node, currentScene),
			NodeType.Item => ResolveItemTargets(nodeId, nodeKey, node, currentScene),
			NodeType.MiningNode
			or NodeType.ItemBag when node.X.HasValue && node.Y.HasValue && node.Z.HasValue =>
				ResolveMutablePositionedEntityTargets(nodeKey, node, currentScene),
			_ when node.X.HasValue && node.Y.HasValue && node.Z.HasValue =>
				ResolvePositionedEntityTargets(nodeKey, node, currentScene),
			_ => Array.Empty<ResolvedQuestTarget>(),
		};
	}

	private ResolvedActionKind ResolveCharacterActionKind(string nodeKey)
	{
		if (_guide.OutEdges(nodeKey, EdgeType.DropsItem).Count > 0)
			return ResolvedActionKind.Kill;
		if (_guide.OutEdges(nodeKey, EdgeType.SellsItem).Count > 0)
			return ResolvedActionKind.Buy;
		return ResolvedActionKind.Talk;
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolveCharacterTargets(
		string nodeKey,
		Node node,
		string currentScene
	)
	{
		var spawnEdges = _guide.OutEdges(nodeKey, EdgeType.HasSpawn);
		if (spawnEdges.Count == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var nodeContext = BuildNodeContext(nodeKey);
		var results = new List<ResolvedQuestTarget>();
		var actionKind = ResolveCharacterActionKind(nodeKey);
		var targetKind = actionKind == ResolvedActionKind.Kill
			? NavigationTargetKind.Enemy
			: NavigationTargetKind.Character;

		for (int i = 0; i < spawnEdges.Count; i++)
		{
			string spawnKey = spawnEdges[i].Target;
			var spawnNode = _guide.GetNode(spawnKey);
			if (
				spawnNode == null
				|| !spawnNode.X.HasValue
				|| !spawnNode.Y.HasValue
				|| !spawnNode.Z.HasValue
			)
				continue;

			var semantic = BuildDirectNavigationSemantic(
				node,
				targetKind,
				actionKind,
				_guide.GetZoneDisplay(spawnNode.Scene)
			);
			var explanation = NavigationExplanationBuilder.Build(
				semantic,
				nodeContext,
				nodeContext
			);

			results.Add(
				new ResolvedQuestTarget(
					nodeKey,
					spawnNode.Scene,
					spawnKey,
					nodeContext,
					nodeContext,
					semantic,
					explanation,
					spawnNode.X.Value,
					spawnNode.Y.Value,
					spawnNode.Z.Value,
					isActionable: true,
					isBlockedPath: IsSceneBlocked(currentScene, spawnNode.Scene)
				)
			);
		}

		return results;
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolveItemTargets(
		int nodeId,
		string nodeKey,
		Node node,
		string currentScene
	)
	{
		int itemIndex = _guide.FindItemIndex(nodeId);
		if (itemIndex < 0)
			return Array.Empty<ResolvedQuestTarget>();

		var sources = _guide.GetItemSources(itemIndex);
		if (sources.Length == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var nodeContext = BuildNodeContext(nodeKey);
		var results = new List<ResolvedQuestTarget>();

		for (int i = 0; i < sources.Length; i++)
		{
			var source = sources[i];
			string sourceKey = _guide.GetNodeKey(source.SourceId);
			var sourceNode = _guide.GetNode(source.SourceId);
			string? sourceScene = _guide.GetSourceScene(source);
			var sourceContext = BuildNodeContext(sourceKey);
			var semantic = BuildDirectNavigationSemantic(
				node,
				NavigationTargetKind.Item,
				ResolvedActionKind.Collect,
				_guide.GetZoneDisplay(sourceScene)
			);
			var explanation = NavigationExplanationBuilder.Build(
				semantic,
				nodeContext,
				sourceContext
			);

			if (sourceNode.Type is NodeType.MiningNode or NodeType.ItemBag)
			{
				var positions = new List<ResolvedPosition>();
				_positionResolvers.Resolve(sourceKey, positions);
				for (int j = 0; j < positions.Count; j++)
				{
					var position = positions[j];
					results.Add(
						new ResolvedQuestTarget(
							sourceKey,
							position.Scene,
							position.SourceKey ?? sourceKey,
							nodeContext,
							sourceContext,
							semantic,
							explanation,
							position.X,
							position.Y,
							position.Z,
							isActionable: position.IsActionable,
							isBlockedPath: IsSceneBlocked(currentScene, position.Scene)
						)
					);
				}
				continue;
			}

			if (source.Positions.Length > 0)
			{
			    for (int j = 0; j < source.Positions.Length; j++)
			    {
			        var pos = source.Positions[j];
			        results.Add(
			            new ResolvedQuestTarget(
			                sourceKey,
			                sourceScene,
			                sourceKey,
			                nodeContext,
			                sourceContext,
			                semantic,
			                explanation,
			                pos.X,
			                pos.Y,
			                pos.Z,
			                isActionable: true,
			                isBlockedPath: IsSceneBlocked(currentScene, sourceScene)
			            )
			        );
			    }
			}
			else if (sourceNode.Type == NodeType.Character && TryResolveCharacterSpawnTargets(
			    sourceKey,
			    nodeContext,
			    sourceContext,
			    semantic,
			    explanation,
			    currentScene,
			    results
			))
			{
			    continue;
			}
			else if (sourceNode.X.HasValue && sourceNode.Y.HasValue && sourceNode.Z.HasValue)
			{
			    results.Add(
			        new ResolvedQuestTarget(
			            sourceKey,
			            sourceScene,
			            sourceKey,
			            nodeContext,
			            sourceContext,
			            semantic,
			            explanation,
			            sourceNode.X.Value,
			            sourceNode.Y.Value,
			            sourceNode.Z.Value,
			            isActionable: true,
			            isBlockedPath: IsSceneBlocked(currentScene, sourceScene)
			        )
			    );
			}
		}

		return results;
	}

	private bool TryResolveCharacterSpawnTargets(
	    string sourceKey,
	    ResolvedNodeContext nodeContext,
	    ResolvedNodeContext sourceContext,
	    ResolvedActionSemantic semantic,
	    NavigationExplanation explanation,
	    string currentScene,
	    List<ResolvedQuestTarget> results
	)
	{
	    var spawnEdges = _guide.OutEdges(sourceKey, EdgeType.HasSpawn);
	    if (spawnEdges.Count == 0)
	        return false;

	    bool emitted = false;
	    for (int i = 0; i < spawnEdges.Count; i++)
	    {
	        string spawnKey = spawnEdges[i].Target;
	        var spawnNode = _guide.GetNode(spawnKey);
	        if (
	            spawnNode == null
	            || !spawnNode.X.HasValue
	            || !spawnNode.Y.HasValue
	            || !spawnNode.Z.HasValue
	        )
	            continue;

	        results.Add(
	            new ResolvedQuestTarget(
	                sourceKey,
	                spawnNode.Scene,
	                spawnKey,
	                nodeContext,
	                sourceContext,
	                semantic,
	                explanation,
	                spawnNode.X.Value,
	                spawnNode.Y.Value,
	                spawnNode.Z.Value,
	                isActionable: true,
	                isBlockedPath: IsSceneBlocked(currentScene, spawnNode.Scene)
	            )
	        );
	        emitted = true;
	    }

	    return emitted;
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolveMutablePositionedEntityTargets(
	    string nodeKey,
	    Node node,
	    string currentScene
	)
	{
		var positions = new List<ResolvedPosition>();
		_positionResolvers.Resolve(nodeKey, positions);
		if (positions.Count == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var nodeContext = BuildNodeContext(nodeKey);
		var actionKind = node.Type == NodeType.MiningNode
			? ResolvedActionKind.Mine
			: ResolvedActionKind.Collect;
		var semantic = BuildDirectNavigationSemantic(
			node,
			NavigationTargetKind.Object,
			actionKind,
			_guide.GetZoneDisplay(node.Scene)
		);
		var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, nodeContext);
		var results = new List<ResolvedQuestTarget>(positions.Count);
		for (int i = 0; i < positions.Count; i++)
		{
			var position = positions[i];
			results.Add(
				new ResolvedQuestTarget(
					nodeKey,
					position.Scene,
					position.SourceKey ?? nodeKey,
					nodeContext,
					nodeContext,
					semantic,
					explanation,
					position.X,
					position.Y,
					position.Z,
					isActionable: position.IsActionable,
					isBlockedPath: IsSceneBlocked(currentScene, position.Scene)
				)
			);
		}
		return results;
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolvePositionedEntityTargets(
		string nodeKey,
		Node node,
		string currentScene
	)
	{
		var nodeContext = BuildNodeContext(nodeKey);
		var actionKind = node.Type == NodeType.MiningNode
			? ResolvedActionKind.Mine
			: node.Type == NodeType.Water ? ResolvedActionKind.Fish : ResolvedActionKind.Collect;
		var targetKind = node.Type == NodeType.Character
			? NavigationTargetKind.Character
			: NavigationTargetKind.Object;
		var semantic = BuildDirectNavigationSemantic(
			node,
			targetKind,
			actionKind,
			_guide.GetZoneDisplay(node.Scene)
		);
		var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, nodeContext);

		return new[]
		{
			new ResolvedQuestTarget(
				nodeKey,
				node.Scene,
				nodeKey,
				nodeContext,
				nodeContext,
				semantic,
				explanation,
				node.X!.Value,
				node.Y!.Value,
				node.Z!.Value,
				isActionable: true,
				isBlockedPath: IsSceneBlocked(currentScene, node.Scene)
			),
		};
	}

	private bool IsSceneBlocked(string currentScene, string? targetScene)
	{
		if (_zoneRouter == null)
			return false;
		if (string.IsNullOrWhiteSpace(currentScene) || string.IsNullOrWhiteSpace(targetScene))
			return false;
		if (string.Equals(currentScene, targetScene, StringComparison.OrdinalIgnoreCase))
			return false;
		return _zoneRouter.FindFirstLockedHop(currentScene, targetScene) != null;
	}

	private static ResolvedActionSemantic BuildDirectNavigationSemantic(
		Node targetNode,
		NavigationTargetKind targetKind,
		ResolvedActionKind actionKind,
		string? zoneText
	)
	{
		return new ResolvedActionSemantic(
			NavigationGoalKind.Generic,
			targetKind,
			actionKind,
			goalNodeKey: null,
			goalQuantity: null,
			keywordText: null,
			payloadText: null,
			targetIdentityText: targetNode.DisplayName,
			contextText: null,
			rationaleText: null,
			zoneText: zoneText,
			availabilityText: null,
			preferredMarkerKind: QuestMarkerKind.Objective,
			markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(
				QuestMarkerKind.Objective
			)
		);
	}
}
