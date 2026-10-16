using AdventureGuide.Data;
using AdventureGuide.State;

namespace AdventureGuide.Navigation;

public readonly struct ZoneLineAccess
{
    public ZoneLineEntry Line { get; }
    public bool Possible { get; }
    public bool Accessible { get; }

    public ZoneLineAccess(ZoneLineEntry line, GateConditions gates)
    {
        Line = line;
        Possible = gates.CanBecomeAvailable(line.Condition);
        Accessible = Possible && gates.IsAvailable(line.Condition);
    }
}

public static class CrossZoneWaypointPolicy
{
    public static bool IsAccessibleSetUnchanged(
        IReadOnlyList<ZoneLineAccess> snapshot,
        GateConditions gates
    )
    {
        for (int i = 0; i < snapshot.Count; i++)
        {
            var previous = snapshot[i];
            bool possible = gates.CanBecomeAvailable(previous.Line.Condition);
            if (
                previous.Possible != possible
                || previous.Accessible != (possible && gates.IsAvailable(previous.Line.Condition))
            )
                return false;
        }
        return true;
    }

    public static bool SceneChanged(string? previous, string current) =>
        !string.Equals(previous, current, StringComparison.OrdinalIgnoreCase);

    public static bool ShouldKeepOnStateChange(
        bool hasLine,
        bool hasWaypoint,
        bool targetUnchanged,
        bool nextHopUnchanged,
        bool entryUnchanged,
        bool accessibleSetUnchanged,
        bool routeLockedUnchanged
    ) =>
        hasLine
        && hasWaypoint
        && targetUnchanged
        && nextHopUnchanged
        && entryUnchanged
        && accessibleSetUnchanged
        && routeLockedUnchanged;

    public static bool ShouldRecalculate(
        bool hasLine,
        bool hasWaypoint,
        float movedSquared,
        float thresholdSquared
    ) => !hasLine || !hasWaypoint || movedSquared > thresholdSquared;

    public static bool ShouldRebuild(
        bool hasWaypoint,
        bool lineChanged,
        bool cachedLocked,
        bool routeLocked
    ) => !hasWaypoint || lineChanged || cachedLocked != routeLocked;
}
