namespace AdventureGuide.Navigation;

internal enum GameMarkerAction
{
    None,
    Hide,
    Restore,
    Spawn,
}

internal static class GameMarkerPolicy
{
    internal static bool IsQuestAvailable(bool held, bool completed) => !held && !completed;

    internal static GameMarkerAction Decide(
        bool suppressed,
        bool useMarkers,
        bool simPlayer,
        bool alive,
        bool eligible,
        bool hasMarker
    )
    {
        if (suppressed || !useMarkers || simPlayer || !alive || !eligible)
            return hasMarker ? GameMarkerAction.Hide : GameMarkerAction.None;
        return hasMarker ? GameMarkerAction.Restore : GameMarkerAction.Spawn;
    }
}
