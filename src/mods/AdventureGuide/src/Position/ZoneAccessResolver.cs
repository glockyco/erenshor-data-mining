using AdventureGuide.Graph;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Position;

/// <summary>
/// Determines whether reaching another scene is blocked by a locked zone line,
/// and if so returns that zone line plus its unlock evaluation.
/// </summary>
public sealed class ZoneAccessResolver
{
    public sealed class LockedRoute
    {
        public Node ZoneLineNode { get; }
        public UnlockEvaluation Evaluation { get; }

        public LockedRoute(Node zoneLineNode, UnlockEvaluation evaluation)
        {
            ZoneLineNode = zoneLineNode;
            Evaluation = evaluation;
        }
    }

    private readonly CompiledGuideModel _guide;
    private readonly QuestStateTracker _tracker;
    private readonly UnlockEvaluator _unlocks;
    private readonly ZoneRouter _router;

    public ZoneAccessResolver(
        CompiledGuideModel guide,
        QuestStateTracker tracker,
        UnlockEvaluator unlocks,
        ZoneRouter router
    )
    {
        _guide = guide;
        _tracker = tracker;
        _unlocks = unlocks;
        _router = router;
    }

    public LockedRoute? FindBlockedRoute(string? targetScene)
    {
        if (
            string.IsNullOrEmpty(_tracker.CurrentZone)
            || string.IsNullOrEmpty(targetScene)
            || string.Equals(_tracker.CurrentZone, targetScene, StringComparison.OrdinalIgnoreCase)
        )
        {
            return null;
        }

        var lockedHop = _router.FindFirstLockedHop(_tracker.CurrentZone, targetScene);
        if (lockedHop == null)
            return null;

        var zoneLine = _guide.GetNode(lockedHop.ZoneLineKey);
        if (zoneLine == null)
            return null;

        var evaluation = _unlocks.Evaluate(zoneLine);
        return evaluation.IsUnlocked ? null : new LockedRoute(zoneLine, evaluation);
    }
}
