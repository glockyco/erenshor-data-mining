using System.Diagnostics;
using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.State;
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
	private readonly GuideReader _reader;
	private readonly PositionResolverRegistry _positionResolvers;
	private readonly QuestTargetProjector _projector;
	private readonly DiagnosticsCore? _diagnostics;
	private string? _lastResolvedNodeKey;
	private int _lastResolvedTargetCount;
	private int _lastBatchKeyCount;
	private IReadOnlyList<QuestCostSample> _topQuestCosts = Array.Empty<QuestCostSample>();

	public int Version => _reader.Engine.Revision;

	internal NavigationTargetResolver(
		CompiledGuideModel guide,
		GuideReader reader,
		ZoneRouter? zoneRouter,
		PositionResolverRegistry positionResolvers,
		QuestTargetProjector projector,
		DiagnosticsCore? diagnostics = null)
	{
		_guide = guide;
		_reader = reader;
		_positionResolvers = positionResolvers;
		_projector = projector;
		_diagnostics = diagnostics;
		_ = zoneRouter;
	}

	public IReadOnlyList<ResolvedQuestTarget> Resolve(
		string nodeKey,
		string currentScene,
		IResolutionTracer? tracer = null)
	{
		var token = _diagnostics?.BeginSpan(
			DiagnosticSpanKind.NavResolverResolve,
			DiagnosticsContext.Root(DiagnosticTrigger.Unknown),
			primaryKey: nodeKey);
		long startTick = Stopwatch.GetTimestamp();
		try
		{
			tracer?.OnResolveBegin(nodeKey);

			if (string.IsNullOrWhiteSpace(nodeKey))
				return Array.Empty<ResolvedQuestTarget>();

			if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
				return Array.Empty<ResolvedQuestTarget>();

			var node = _guide.GetNode(nodeId);
			IReadOnlyList<ResolvedQuestTarget> results = node.Type == NodeType.Quest
				? (tracer != null
					? _reader.ReadQuestResolutionForTrace(nodeKey, currentScene, tracer).NavigationTargets
					: _reader.ReadQuestResolution(nodeKey, currentScene).NavigationTargets)
				: ResolveNonQuestEntity(nodeId, nodeKey, node, currentScene);

			_lastResolvedNodeKey = nodeKey;
			_lastBatchKeyCount = 1;
			_topQuestCosts = Array.Empty<QuestCostSample>();
			_lastResolvedTargetCount = results.Count;
			tracer?.OnResolveEnd(results.Count);
			return results;
		}
		finally
		{
			if (token != null)
				_diagnostics!.EndSpan(
					token.Value,
					Stopwatch.GetTimestamp() - startTick,
					value0: _lastResolvedTargetCount,
					value1: 0);
		}
	}

	internal IReadOnlyDictionary<string, IReadOnlyList<ResolvedQuestTarget>> ResolveBatch(
		IEnumerable<string> nodeKeys,
		string currentScene,
		IResolutionTracer? tracer = null)
	{
		var results = new Dictionary<string, IReadOnlyList<ResolvedQuestTarget>>(StringComparer.Ordinal);
		var questKeys = new List<string>();
		var seen = new HashSet<string>(StringComparer.Ordinal);
		int totalResolvedTargets = 0;
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

			var nonQuestResults = ResolveNonQuestEntity(nodeId, nodeKey, node, currentScene);
			results[nodeKey] = nonQuestResults;
			totalResolvedTargets += nonQuestResults.Count;
		}

		_lastBatchKeyCount = seen.Count;
		_topQuestCosts = Array.Empty<QuestCostSample>();
		for (int i = 0; i < questKeys.Count; i++)
		{
			string questKey = questKeys[i];
			var navigationTargets = _reader.ReadQuestResolution(questKey, currentScene).NavigationTargets;
			results[questKey] = navigationTargets;
			totalResolvedTargets += navigationTargets.Count;
		}

		_lastResolvedTargetCount = totalResolvedTargets;
		_ = tracer;
		return results;
	}

	internal NavigationDiagnosticsSnapshot ExportDiagnosticsSnapshot()
	{
		return new NavigationDiagnosticsSnapshot(
			lastForceReason: DiagnosticTrigger.Unknown,
			cacheEntryCount: 0,
			currentTargetKey: _lastResolvedNodeKey,
			lastResolvedTargetCount: _lastResolvedTargetCount,
			lastBatchKeyCount: _lastBatchKeyCount,
			lastBatchWasPartialRefresh: false,
			topQuestCosts: _topQuestCosts);
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolveNonQuestEntity(
		int nodeId,
		string nodeKey,
		Node node,
		string currentScene)
	{
		return node.Type switch
		{
			NodeType.Character => ResolveCharacterTargets(nodeKey, node, currentScene),
			NodeType.Item => ResolveItemTargets(nodeId, nodeKey, node, currentScene),
			NodeType.MiningNode or NodeType.ItemBag when node.X.HasValue && node.Y.HasValue && node.Z.HasValue =>
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
		string currentScene)
	{
		var spawnEdges = _guide.OutEdges(nodeKey, EdgeType.HasSpawn);
		if (spawnEdges.Count == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var nodeContext = _projector.BuildNodeContext(nodeKey);
		var results = new List<ResolvedQuestTarget>();
		var actionKind = ResolveCharacterActionKind(nodeKey);
		var targetKind = actionKind == ResolvedActionKind.Kill
			? NavigationTargetKind.Enemy
			: NavigationTargetKind.Character;

		for (int i = 0; i < spawnEdges.Count; i++)
		{
			string spawnKey = spawnEdges[i].Target;
			var spawnNode = _guide.GetNode(spawnKey);
			if (spawnNode == null || !spawnNode.X.HasValue || !spawnNode.Y.HasValue || !spawnNode.Z.HasValue)
				continue;

			var semantic = BuildDirectNavigationSemantic(
				node,
				targetKind,
				actionKind,
				_guide.GetZoneDisplay(spawnNode.Scene));
			var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, nodeContext);

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
					isBlockedPath: _projector.IsSceneBlocked(currentScene, spawnNode.Scene)));
		}

		return results;
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolveItemTargets(
		int nodeId,
		string nodeKey,
		Node node,
		string currentScene)
	{
		int itemIndex = _guide.FindItemIndex(nodeId);
		if (itemIndex < 0)
			return Array.Empty<ResolvedQuestTarget>();

		var sources = _guide.GetItemSources(itemIndex);
		if (sources.Length == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var nodeContext = _projector.BuildNodeContext(nodeKey);
		var results = new List<ResolvedQuestTarget>();

		for (int i = 0; i < sources.Length; i++)
		{
			var source = sources[i];
			string sourceKey = _guide.GetNodeKey(source.SourceId);
			var sourceNode = _guide.GetNode(source.SourceId);
			string? sourceScene = _guide.GetSourceScene(source);
			var sourceContext = _projector.BuildNodeContext(sourceKey);
			var semantic = BuildDirectNavigationSemantic(
				node,
				NavigationTargetKind.Item,
				ResolvedActionKind.Collect,
				_guide.GetZoneDisplay(sourceScene));
			var explanation = NavigationExplanationBuilder.Build(semantic, nodeContext, sourceContext);

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
							isBlockedPath: _projector.IsSceneBlocked(currentScene, position.Scene)));
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
							isBlockedPath: _projector.IsSceneBlocked(currentScene, sourceScene)));
				}
			}
			else if (sourceNode.Type == NodeType.Character && TryResolveCharacterSpawnTargets(
				sourceKey,
				nodeContext,
				sourceContext,
				semantic,
				explanation,
				currentScene,
				results))
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
						isBlockedPath: _projector.IsSceneBlocked(currentScene, sourceScene)));
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
		List<ResolvedQuestTarget> results)
	{
		var spawnEdges = _guide.OutEdges(sourceKey, EdgeType.HasSpawn);
		if (spawnEdges.Count == 0)
			return false;

		bool emitted = false;
		for (int i = 0; i < spawnEdges.Count; i++)
		{
			string spawnKey = spawnEdges[i].Target;
			var spawnNode = _guide.GetNode(spawnKey);
			if (spawnNode == null || !spawnNode.X.HasValue || !spawnNode.Y.HasValue || !spawnNode.Z.HasValue)
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
					isBlockedPath: _projector.IsSceneBlocked(currentScene, spawnNode.Scene)));
			emitted = true;
		}

		return emitted;
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolveMutablePositionedEntityTargets(
		string nodeKey,
		Node node,
		string currentScene)
	{
		var positions = new List<ResolvedPosition>();
		_positionResolvers.Resolve(nodeKey, positions);
		if (positions.Count == 0)
			return Array.Empty<ResolvedQuestTarget>();

		var nodeContext = _projector.BuildNodeContext(nodeKey);
		var actionKind = node.Type == NodeType.MiningNode ? ResolvedActionKind.Mine : ResolvedActionKind.Collect;
		var semantic = BuildDirectNavigationSemantic(
			node,
			NavigationTargetKind.Object,
			actionKind,
			_guide.GetZoneDisplay(node.Scene));
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
					isBlockedPath: _projector.IsSceneBlocked(currentScene, position.Scene)));
		}
		return results;
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolvePositionedEntityTargets(
		string nodeKey,
		Node node,
		string currentScene)
	{
		var nodeContext = _projector.BuildNodeContext(nodeKey);
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
			_guide.GetZoneDisplay(node.Scene));
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
				isBlockedPath: _projector.IsSceneBlocked(currentScene, node.Scene))
		};
	}

	private static ResolvedActionSemantic BuildDirectNavigationSemantic(
		Node targetNode,
		NavigationTargetKind targetKind,
		ResolvedActionKind actionKind,
		string? zoneText)
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
			markerPriority: ResolvedActionSemanticBuilder.GetMarkerPriority(QuestMarkerKind.Objective));
	}
}
