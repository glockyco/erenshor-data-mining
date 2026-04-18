using AdventureGuide.Plan;
using AdventureGuide.Position;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution;

/// <summary>
/// Canonical quest-target derivation shared by navigation, tracker summaries,
/// and marker resolution.
/// </summary>
public sealed class QuestTargetResolver
{
	private readonly CompiledGuideModel _guide;
	private readonly EffectiveFrontier _frontier;
	private readonly SourceResolver _sourceResolver;
	private readonly ZoneRouter? _zoneRouter;
	private readonly Func<int> _versionProvider;
	private readonly Dictionary<string, IReadOnlyList<ResolvedTarget>> _questTargetCache = new(
		StringComparer.Ordinal
	);
	private int _cachedQuestTargetVersion = -1;

	public QuestTargetResolver(
		CompiledGuideModel guide,
		EffectiveFrontier frontier,
		SourceResolver sourceResolver,
		ZoneRouter? zoneRouter,
		Func<int>? versionProvider = null
	)
	{
		_guide = guide;
		_frontier = frontier;
		_sourceResolver = sourceResolver;
		_zoneRouter = zoneRouter;
		_versionProvider = versionProvider ?? (() => 0);
	}

	public int Version => _versionProvider();

	public IReadOnlyList<ResolvedTarget> Resolve(
		int questIndex,
		string currentScene,
		IResolutionTracer? tracer = null
	) => Resolve(questIndex, currentScene, session: null, tracer);

	internal IReadOnlyList<ResolvedTarget> Resolve(
		int questIndex,
		string currentScene,
		SourceResolver.ResolutionSession? session,
		IResolutionTracer? tracer = null
	)
	{
		int version = Version;
		if (_cachedQuestTargetVersion != version)
		{
			_questTargetCache.Clear();
			_cachedQuestTargetVersion = version;
		}

		string cacheKey = BuildQuestCacheKey(_guide.GetNodeKey(_guide.QuestNodeId(questIndex)), currentScene);
		if (_questTargetCache.TryGetValue(cacheKey, out var cached))
			return cached;

		var questNode = _guide.GetNode(_guide.QuestNodeId(questIndex));
		tracer?.OnQuestPhase(questIndex, questNode.DbName, "resolving");

		var frontier = new List<FrontierEntry>();
		_frontier.Resolve(questIndex, frontier, -1, tracer);

		var results = new List<ResolvedTarget>();
		var seenTargets = new HashSet<string>(StringComparer.Ordinal);
		var resolutionSession = session ?? new SourceResolver.ResolutionSession();
		for (int i = 0; i < frontier.Count; i++)
		{
			var compiledTargets = CollapseCrossZoneTargets(
				_sourceResolver.ResolveTargets(frontier[i], currentScene, resolutionSession, tracer),
				currentScene
			);
			for (int j = 0; j < compiledTargets.Count; j++)
				TryAddResolvedTarget(results, compiledTargets[j], seenTargets);
		}

		if (results.Count > 1)
		{
		    results.Sort((left, right) =>
		        left.AvailabilityPriority == right.AvailabilityPriority
		            ? 0
		            : left.AvailabilityPriority < right.AvailabilityPriority ? -1 : 1
		    );
		}

		IReadOnlyList<ResolvedTarget> frozen = results.Count == 0
		    ? Array.Empty<ResolvedTarget>()
		    : results;
		_questTargetCache[cacheKey] = frozen;
		return frozen;
	}

	private void TryAddResolvedTarget(
		List<ResolvedTarget> results,
		ResolvedTarget target,
		HashSet<string> seenTargets
	)
	{
		string dedupeKey = BuildResolvedTargetDedupeKey(target);
		if (!seenTargets.Add(dedupeKey))
			return;

		results.Add(target);
	}

	private string BuildResolvedTargetDedupeKey(ResolvedTarget target)
	{
		string questKey = _guide.GetNodeKey(_guide.QuestNodeId(target.QuestIndex));
		string goalKey = string.IsNullOrEmpty(target.Semantic.GoalNodeKey)
			? _guide.GetNodeKey(target.TargetNodeId)
			: target.Semantic.GoalNodeKey;
		return TargetInstanceIdentity.BuildDedupeKey(
			questKey,
			goalKey,
			_guide.GetNodeKey(target.TargetNodeId),
			target.Scene,
			_guide.GetNodeKey(target.PositionNodeId)
		);
	}

	private IReadOnlyList<ResolvedTarget> CollapseCrossZoneTargets(
		IReadOnlyList<ResolvedTarget> targets,
		string currentScene
	)
	{
		if (targets.Count < 2)
			return targets;

		var collapsed = new List<ResolvedTarget>(targets.Count);
		var seenCrossZoneScenes = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
		for (int i = 0; i < targets.Count; i++)
		{
			var target = targets[i];
			bool sameScene =
				target.Scene == null
				|| string.Equals(target.Scene, currentScene, StringComparison.OrdinalIgnoreCase);
			if (sameScene)
			{
				collapsed.Add(target);
				continue;
			}

			bool blocked = IsSceneBlocked(currentScene, target.Scene);
			string sceneKey = (blocked ? "blocked|" : "direct|") + target.Scene;
			if (seenCrossZoneScenes.Add(sceneKey))
				collapsed.Add(target);
		}

		return collapsed.Count == targets.Count ? targets : collapsed;
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

	private static string BuildQuestCacheKey(string nodeKey, string currentScene) =>
		nodeKey + "\n" + (currentScene ?? string.Empty).ToUpperInvariant();
}
