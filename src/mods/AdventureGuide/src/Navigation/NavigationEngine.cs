using AdventureGuide.Views;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Position;
using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Navigation projection over shared quest resolution outputs.
/// Resolves selected targets only when navigation state changes, then performs
/// cheap proximity picking and per-frame live tracking.
/// </summary>
public sealed class NavigationEngine
{
    private readonly NavigationSet _navSet;
    private readonly EntityGraph _graph;
    private readonly QuestResolutionService _resolution;
    private readonly QuestStateTracker _tracker;
    private readonly ZoneRouter _router;
    private readonly LiveStateTracker _liveState;
    private readonly EntityRegistry _entities;
    private readonly UnlockEvaluator _unlocks;

    private readonly List<Candidate> _candidates = new();

    public string? TargetNodeKey { get; private set; }
    public Vector3? TargetPosition { get; private set; }
    public string? TargetScene { get; private set; }
    public Vector3? EffectiveTarget { get; private set; }
    public NavigationExplanation? Explanation { get; private set; }
    public bool HasTarget => EffectiveTarget.HasValue;
    public float Distance { get; private set; }
    public string CurrentScene { get; private set; } = "";
    public int HopCount { get; private set; }

    private int _lastNavSetVersion = -1;
    private int _lastTrackerVersion = -1;
    private int _lastLiveVersion = -1;
    private string _lastResolveScene = "";

    private const float RePickInterval = 0.5f;
    private float _rePickTimer;

    private string? _cachedRouteFrom;
    private string? _cachedRouteTo;
    private ZoneRouter.Route? _cachedRoute;

    public NavigationEngine(
        NavigationSet navSet,
        EntityGraph graph,
        QuestResolutionService resolution,
        QuestStateTracker tracker,
        ZoneRouter router,
        EntityRegistry entities,
        LiveStateTracker liveState,
        UnlockEvaluator unlocks)
    {
        _navSet = navSet;
        _graph = graph;
        _resolution = resolution;
        _tracker = tracker;
        _router = router;
        _entities = entities;
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

        bool navChanged = _navSet.Version != _lastNavSetVersion;
        bool stateChanged = _tracker.Version != _lastTrackerVersion;
        bool liveChanged = _liveState.Version != _lastLiveVersion;
        bool sceneChanged = !string.Equals(CurrentScene, _lastResolveScene, StringComparison.OrdinalIgnoreCase);

        if (navChanged || stateChanged || liveChanged || sceneChanged)
        {
            if (stateChanged)
            {
                _cachedRouteFrom = null;
                _cachedRouteTo = null;
                _cachedRoute = null;
                _router.Rebuild();
            }

            _lastNavSetVersion = _navSet.Version;
            _lastTrackerVersion = _tracker.Version;
            _lastLiveVersion = _liveState.Version;
            _lastResolveScene = CurrentScene;
            Resolve(playerPosition);
            _rePickTimer = 0f;
        }

        _rePickTimer += Time.deltaTime;
        if (_rePickTimer >= RePickInterval && _candidates.Count > 1)
        {
            _rePickTimer = 0f;
            PickClosest(playerPosition);
        }

        Track(playerPosition);
    }

    private void Resolve(Vector3 playerPosition)
    {
        _candidates.Clear();
        foreach (var key in _navSet.Keys)
            ResolveKey(key);

        if (_candidates.Count == 0)
        {
            ClearTarget();
            return;
        }

        PickClosest(playerPosition);
    }

    private void ResolveKey(string nodeKey)
    {
        EntityViewNode? context = null;
        if (_navSet.TryGetContext(nodeKey, out var storedContext))
            context = storedContext;

        var targets = _resolution.ResolveTargetsForNavigation(nodeKey, context);
        for (int i = 0; i < targets.Count; i++)
        {
            var target = targets[i];
            _candidates.Add(new Candidate(
                nodeKey,
                target.TargetNodeKey,
                target.Position,
                target.Scene,
                target.SourceKey,
                target.Semantic,
                target.Explanation,
                target.IsActionable));
        }
    }

    private void PickClosest(Vector3 playerPosition)
    {
        const float NonActionablePenalty = 500_000f;
        const float CrossZonePenalty = 1_000_000f;

        float bestScore = float.MaxValue;
        Candidate? best = null;

        for (int i = 0; i < _candidates.Count; i++)
        {
            var candidate = _candidates[i];

            bool sameScene = string.Equals(candidate.Scene, CurrentScene, StringComparison.OrdinalIgnoreCase)
                || candidate.Scene == null;
            bool zoneExit = sameScene && candidate.Semantic.GoalKind == NavigationGoalKind.TravelToZone;
            float score = (candidate.Position - playerPosition).sqrMagnitude;
            if (!sameScene || zoneExit)
                score += CrossZonePenalty;
            else if (!candidate.IsActionable)
                score += NonActionablePenalty;

            if (score < bestScore)
            {
                bestScore = score;
                best = candidate;
            }
        }

        if (best == null)
        {
            ClearTarget();
            return;
        }

        TargetNodeKey = best.Value.NodeKey;
        TargetPosition = best.Value.Position;
        TargetScene = best.Value.Scene;
        EffectiveTarget = best.Value.Position;
        Explanation = ApplySourceGateDetail(
            ApplyLiveActionOverride(best.Value.Semantic, best.Value.Explanation, best.Value.SourceKey),
            best.Value.SourceKey);
        HopCount = 0;

        bool targetInOtherZone = best.Value.Scene != null
            && !string.Equals(best.Value.Scene, CurrentScene, StringComparison.OrdinalIgnoreCase);
        if (targetInOtherZone)
        {
            var route = FindRouteCached(CurrentScene, best.Value.Scene!);
            if (route != null)
            {
                EffectiveTarget = new Vector3(route.X, route.Y, route.Z);
                HopCount = Math.Max(0, route.Path.Count - 1);
            }
        }
    }

    private NavigationExplanation ApplyLiveActionOverride(
        ResolvedActionSemantic semantic,
        NavigationExplanation explanation,
        string? sourceKey)
    {
        if (semantic.ActionKind != ResolvedActionKind.Kill || sourceKey == null)
            return explanation;

        var sourceNode = _graph.GetNode(sourceKey);
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
            var targetNode = _graph.GetNode(TargetNodeKey);
            if (targetNode?.Type == NodeType.Character)
            {
                var liveNpc = _entities.FindClosest(TargetNodeKey, playerPosition);
                if (liveNpc != null)
                    EffectiveTarget = liveNpc.transform.position;
            }
        }

        Distance = EffectiveTarget.HasValue
            ? Vector3.Distance(playerPosition, EffectiveTarget.Value)
            : 0f;
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
    }

    private readonly struct Candidate
    {
        public readonly string RequestedKey;
        public readonly string NodeKey;
        public readonly Vector3 Position;
        public readonly string? Scene;
        public readonly string? SourceKey;
        public readonly NavigationExplanation Explanation;
        public readonly ResolvedActionSemantic Semantic;
        public readonly bool IsActionable;

        public Candidate(
            string requestedKey,
            string nodeKey,
            Vector3 position,
            string? scene,
            string? sourceKey,
            ResolvedActionSemantic semantic,
            NavigationExplanation explanation,
            bool isActionable = true)
        {
            RequestedKey = requestedKey;
            NodeKey = nodeKey;
            Position = position;
            Scene = scene;
            SourceKey = sourceKey;
            Semantic = semantic;
            Explanation = explanation;
            IsActionable = isActionable;
        }
    }
}
