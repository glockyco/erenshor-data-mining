using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Navigation.Queries;

public sealed class NavigationTargetSnapshotsQuery
{
	private readonly CompiledGuideModel _guide;
	private readonly NavigationTargetResolver _resolver;
	private readonly Query<Unit, SelectorTargetSet> _selectorTargetSet;
	private readonly Query<(string QuestKey, string Scene), QuestResolutionRecord> _questResolution;
	private readonly Dictionary<string, Dictionary<string, NavigationTargetSnapshot>> _snapshotCacheByScene =
		new(StringComparer.Ordinal);
	private readonly Action? _onCompute;

	public Query<string, NavigationTargetSnapshots> Query { get; }

	public NavigationTargetSnapshotsQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		NavigationTargetResolver resolver,
		SelectorTargetSetQuery selectorTargetSet,
		QuestResolutionQuery questResolution)
		: this(engine, guide, resolver, selectorTargetSet.Query, questResolution.Query, onCompute: null)
	{
	}

	internal NavigationTargetSnapshotsQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		NavigationTargetResolver resolver,
		Query<Unit, SelectorTargetSet> selectorTargetSet,
		Query<(string QuestKey, string Scene), QuestResolutionRecord> questResolution,
		Action? onCompute)
	{
		_guide = guide;
		_resolver = resolver;
		_selectorTargetSet = selectorTargetSet;
		_questResolution = questResolution;
		_onCompute = onCompute;
		Query = engine.DefineQuery<string, NavigationTargetSnapshots>(
			name: "NavigationTargetSnapshots",
			compute: Compute);
	}

	private NavigationTargetSnapshots Compute(ReadContext<FactKey> ctx, string scene)
	{
		_onCompute?.Invoke();
		var selectorTargetSet = ctx.Read(_selectorTargetSet, Unit.Value);
		if (selectorTargetSet.Keys.Count == 0)
		{
			_snapshotCacheByScene.Clear();
			return new NavigationTargetSnapshots(scene, Array.Empty<NavigationTargetSnapshot>());
		}

		using var _ = CompiledTargetsQuery.BeginSharedResolutionBatchScope();
		var cache = GetSceneCache(scene);
		var snapshots = new List<NavigationTargetSnapshot>(selectorTargetSet.Keys.Count);
		var activeKeys = new HashSet<string>(StringComparer.Ordinal);
		for (int i = 0; i < selectorTargetSet.Keys.Count; i++)
		{
			string nodeKey = selectorTargetSet.Keys[i];
			var targets = ResolveTargets(ctx, nodeKey, scene);
			if (!cache.TryGetValue(nodeKey, out var snapshot) || !ReferenceEquals(snapshot.Targets, targets))
			{
				snapshot = new NavigationTargetSnapshot(nodeKey, scene, targets);
				cache[nodeKey] = snapshot;
			}

			snapshots.Add(snapshot);
			activeKeys.Add(nodeKey);
		}

		PruneStaleCaches(activeKeys);
		return new NavigationTargetSnapshots(scene, snapshots);
	}

	private IReadOnlyList<ResolvedQuestTarget> ResolveTargets(
		ReadContext<FactKey> ctx,
		string nodeKey,
		string scene)
	{
		if (!_guide.TryGetNodeId(nodeKey, out int nodeId))
			return Array.Empty<ResolvedQuestTarget>();

		var node = _guide.GetNode(nodeId);
		return node.Type == NodeType.Quest
			? ctx.Read(_questResolution, (nodeKey, scene)).NavigationTargets
			: _resolver.ResolveNonQuest(nodeKey, scene);
	}

	private void PruneStaleCaches(HashSet<string> activeKeys)
	{
		foreach (var sceneEntry in _snapshotCacheByScene.ToArray())
		{
			var cache = sceneEntry.Value;
			foreach (var staleKey in cache.Keys.Except(activeKeys, StringComparer.Ordinal).ToArray())
				cache.Remove(staleKey);

			if (cache.Count == 0)
				_snapshotCacheByScene.Remove(sceneEntry.Key);
		}
	}

	private Dictionary<string, NavigationTargetSnapshot> GetSceneCache(string scene)
	{
		if (_snapshotCacheByScene.TryGetValue(scene, out var cache))
			return cache;

		cache = new Dictionary<string, NavigationTargetSnapshot>(StringComparer.Ordinal);
		_snapshotCacheByScene.Add(scene, cache);
		return cache;
	}
}
