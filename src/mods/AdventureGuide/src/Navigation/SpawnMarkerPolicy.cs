namespace AdventureGuide.Navigation;

internal static class SpawnMarkerPolicy
{
    internal static MarkerType? TypeWhenTargetLost(SpawnPointPhase phase) =>
        phase switch
        {
            SpawnPointPhase.NightLocked => MarkerType.NightSpawn,
            SpawnPointPhase.Respawning => MarkerType.DeadSpawn,
            _ => null,
        };

    internal static bool ResetReady(int resetFrame, int currentFrame) =>
        resetFrame >= 0 && currentFrame > resetFrame;
}
