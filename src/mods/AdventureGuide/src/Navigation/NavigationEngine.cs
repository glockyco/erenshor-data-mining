using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Position;
using UnityEngine;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Navigation;

/// <summary>
/// Navigation projection over shared quest resolution outputs.
/// Resolves selected targets only when navigation state changes, then performs
/// cheap proximity picking and per-frame live tracking.
/// </summary>
public sealed class NavigationEngine
{
	private readonly NavigationSet _navSet;
	private readonly CompiledGuideModel _guide;
	private readonly Func<int> _targetSourceVersion;
	private readonly NavigationTargetSelector _selector;
	private readonly ZoneRouter _router;
	private readonly LiveStateTracker _liveState;
	private readonly UnlockEvaluator _unlocks;

	public string? TargetNodeKey { get; private set; }
	public Vector3? TargetPosition { get; private set; }
	public string? TargetScene { get; private set; }
	public Vector3? EffectiveTarget { get; private set; }
	public NavigationExplanation? Explanation { get; private set; }
	public bool HasTarget => EffectiveTarget.HasValue;
	public float Distance { get; private set; }
	public string CurrentScene { get; private set; } = "";
	public int HopCount { get; private set; }

	private int _lastNavSetVersion    = -1;
	private int _lastSelectorVersion  = -1;
	private int _lastResolutionVersion = -1;
	private string _lastResolveScene = "";

	private string? _cachedRouteFrom;
	private string? _cachedRouteTo;
	private ZoneRouter.Route? _cachedRoute;

	// Concrete positioned source for the current target. For multi-spawn
	// characters, NAV follows this source's occupant rather than rescanning all
	// equivalent characters globally each frame.
	private string? _targetSourceKey;

	public NavigationEngine(
		NavigationSet navSet,
		CompiledGuideModel guide,
		Func<int> targetSourceVersion,
		NavigationTargetSelector selector,
		ZoneRouter router,
		LiveStateTracker liveState,
		UnlockEvaluator unlocks)
	{
		_navSet = navSet;
		_guide = guide;
		_targetSourceVersion = targetSourceVersion;
		_selector = selector;
		_router = router;
		_liveState = liveState;
		_unlocks = unlocks;
	}

	public void OnSceneChanged(string sceneName)
	{
		CurrentScene = sceneName;
		_cachedRouteFrom = null;
		_cachedRouteTo = null;
		_cachedRoute = null;
		_router.Rebuild();
		_lastResolveScene = "";
	}

	public void Update(Vector3 playerPosition)
	{
		if (_navSet.Keys.Count == 0)
		{
			ClearTarget();
			return;
		}

		bool navChanged      = _navSet.Version   != _lastNavSetVersion;
		bool selectorChanged = _selector.Version != _lastSelectorVersion;
		int targetSourceVersion = _targetSourceVersion();
		bool sourceChanged   = targetSourceVersion != _lastResolutionVersion;
		bool sceneChanged    = !string.Equals(CurrentScene, _lastResolveScene, StringComparison.OrdinalIgnoreCase);

		if (navChanged || selectorChanged || sceneChanged)
		{
			// Router accessibility depends on unlock state, not player position.
			// Only rebuild when the navigation target source changed or the
			// scene changed.
			if (sourceChanged || sceneChanged)
			{
				_cachedRouteFrom = null;
				_cachedRouteTo   = null;
				_cachedRoute     = null;
				_router.Rebuild();
			}

			_lastNavSetVersion     = _navSet.Version;
			_lastSelectorVersion   = _selector.Version;
			_lastResolutionVersion = targetSourceVersion;
			_lastResolveScene      = CurrentScene;
		}

		Resolve(playerPosition);
		Track(playerPosition);
	}

	private void Resolve(Vector3 playerPosition)
	{
		ResolvedQuestTarget? best = null;
		float bestScore = float.MaxValue;

		foreach (var key in _navSet.Keys)
		{
			if (!_selector.TryGet(key, out var sel))
				continue;

			float score = ComputeNavScore(sel, playerPosition);
			if (score < bestScore)
			{
				bestScore = score;
				best = sel.Target;
			}
		}

		if (best == null)
		{
			ClearTarget();
			return;
		}

		SetTarget(best);
	}

	private static float ComputeNavScore(SelectedNavTarget sel, Vector3 playerPos) =>
		NavigationScore.Compute(sel, playerPos.x, playerPos.y, playerPos.z);

	private void SetTarget(ResolvedQuestTarget target)
	{
		TargetNodeKey   = target.TargetNodeKey;
		TargetPosition  = new Vector3(target.X, target.Y, target.Z);
		TargetScene     = target.Scene;
		EffectiveTarget = new Vector3(target.X, target.Y, target.Z);
		Explanation = ApplySourceGateDetail(
			ApplyLiveActionOverride(target.Semantic, target.Explanation, target.SourceKey),
			target.SourceKey);
		HopCount = 0;
		_targetSourceKey = target.SourceKey;

		bool targetInOtherZone = target.Scene != null
			&& !string.Equals(target.Scene, CurrentScene, StringComparison.OrdinalIgnoreCase);
		if (targetInOtherZone)
		{
			var route = FindRouteCached(CurrentScene, target.Scene!);
			if (route != null)
			{
				EffectiveTarget = new Vector3(route.X, route.Y, route.Z);
				HopCount = Math.Max(0, route.Path.Count - 1);
			}

			// When the only available route passes through a locked zone line,
			// annotate the explanation so the player knows what to complete first.
			if (route != null && route.IsLocked && Explanation != null)
			{
				var lockedHop = _router.FindFirstLockedHop(CurrentScene, target.Scene!);
				if (lockedHop != null)
				{
					string? lockReason = _unlocks.GetRequirementReason(lockedHop.ZoneLineKey);
					if (!string.IsNullOrEmpty(lockReason))
					{
						Explanation = new NavigationExplanation(
							Explanation.GoalKind, Explanation.TargetKind,
							Explanation.GoalNode, Explanation.TargetNode,
							Explanation.PrimaryText, Explanation.TargetIdentityText,
							Explanation.ZoneText, Explanation.SecondaryText,
							lockReason);
					}
				}
			}
		}
	}

	private NavigationExplanation ApplyLiveActionOverride(
		ResolvedActionSemantic semantic,
		NavigationExplanation explanation,
		string? sourceKey)
	{
		if (semantic.ActionKind == ResolvedActionKind.LootChest)
			return explanation;
		if (semantic.ActionKind != ResolvedActionKind.Kill || sourceKey == null)
			return explanation;

		var sourceNode = _guide.GetNode(sourceKey);
		if (sourceNode == null)
			return explanation;

		SpawnInfo info = sourceNode.Type switch
		{
			NodeType.SpawnPoint => _liveState.GetSpawnState(sourceNode),
			NodeType.Character => _liveState.GetCharacterState(sourceNode),
			_ => default,
		};

		if (info.State is SpawnDead && info.LiveNPC != null && info.LiveNPC.gameObject != null)
			return NavigationExplanationBuilder.BuildCorpseExplanation(
				semantic,
				explanation.GoalNode,
				explanation.TargetNode);

		return explanation;
	}

	private NavigationExplanation ApplySourceGateDetail(NavigationExplanation explanation, string? sourceKey)
	{
		if (sourceKey == null)
			return explanation;

		string? reason = _unlocks.GetRequirementReason(sourceKey);
		if (string.IsNullOrEmpty(reason))
			return explanation;

		return new NavigationExplanation(
			explanation.GoalKind,
			explanation.TargetKind,
			explanation.GoalNode,
			explanation.TargetNode,
			explanation.PrimaryText,
			explanation.TargetIdentityText,
			explanation.ZoneText,
			explanation.SecondaryText,
			reason);
	}

	private void Track(Vector3 playerPosition)
	{
		if (TargetNodeKey == null || !TargetPosition.HasValue)
		{
			Distance = 0f;
			return;
		}

		bool isSameScene = string.Equals(TargetScene, CurrentScene, StringComparison.OrdinalIgnoreCase)
			|| TargetScene == null;
		if (isSameScene)
		{
			var livePos = TryGetTrackedLivePosition(playerPosition);
			if (livePos != null)
				EffectiveTarget = new Vector3(
					livePos.Value.x,
					livePos.Value.y,
					livePos.Value.z);
		}

		Distance = EffectiveTarget.HasValue
			? Vector3.Distance(playerPosition, EffectiveTarget.Value)
			: 0f;
	}

	private (float x, float y, float z)? TryGetTrackedLivePosition(Vector3 playerPosition)
	{
		if (_targetSourceKey != null)
		{
			var sourceNode = _guide.GetNode(_targetSourceKey);
			if (sourceNode?.Type == NodeType.SpawnPoint)
				return _liveState.GetLiveNpcPosition(sourceNode);
		}

		var liveNpc = FindLiveNpcBySpawnEdges(playerPosition);
		if (liveNpc == null) return null;

		var pos = liveNpc.transform.position;
		return (pos.x, pos.y, pos.z);
	}

	/// <summary>
	/// Fallback for character targets that have no concrete spawn-source key.
	/// Walks the target character's HasSpawn edges and returns the closest alive
	/// NPC via SpawnPoint.SpawnedNPC references.
	/// </summary>
	private NPC? FindLiveNpcBySpawnEdges(Vector3 playerPosition)
	{
		if (TargetNodeKey == null) return null;
		var characterNode = _guide.GetNode(TargetNodeKey);
		if (characterNode?.Type != NodeType.Character) return null;

		var spawnEdges = _guide.OutEdges(TargetNodeKey, EdgeType.HasSpawn);
		NPC? best = null;
		float bestDist = float.MaxValue;

		for (int i = 0; i < spawnEdges.Count; i++)
		{
			var spawnNode = _guide.GetNode(spawnEdges[i].Target);
			if (spawnNode == null) continue;
			var npc = _liveState.GetLiveNpcForTracking(spawnNode);
			if (npc == null) continue;
			float dist = Vector3.Distance(playerPosition, npc.transform.position);
			if (dist < bestDist) { bestDist = dist; best = npc; }
		}
		return best;
	}

	private ZoneRouter.Route? FindRouteCached(string from, string to)
	{
		if (from == _cachedRouteFrom && to == _cachedRouteTo)
			return _cachedRoute;

		_cachedRouteFrom = from;
		_cachedRouteTo = to;
		_cachedRoute = _router.FindRoute(from, to);
		return _cachedRoute;
	}

	private void ClearTarget()
	{
		TargetNodeKey = null;
		TargetPosition = null;
		TargetScene = null;
		EffectiveTarget = null;
		Explanation = null;
		HopCount = 0;
		Distance = 0f;
		_targetSourceKey = null;
	}
}
