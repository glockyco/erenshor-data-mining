namespace AdventureGuide.Navigation;

public static class CrossZoneWaypointPolicy
{
    public static bool SceneChanged(string? previous, string current) =>
        !string.Equals(previous, current, StringComparison.OrdinalIgnoreCase);

    public static bool ShouldRebuild(
        bool hasWaypoint,
        bool lineChanged,
        bool cachedLocked,
        bool routeLocked
    ) => !hasWaypoint || lineChanged || cachedLocked != routeLocked;
}
