namespace AdventureGuide.Navigation;

/// <summary>Which spawn points without a quest target show respawn timers.</summary>
internal enum RespawnTimerScope
{
    None,
    BossesAndElites,
    All,
}

internal static class RespawnTimerPolicy
{
    /// <summary>ShowAllRespawnTimers includes boss and elite spawn points.</summary>
    public static RespawnTimerScope Scope(bool showAll, bool showBossesAndElites) =>
        showAll ? RespawnTimerScope.All
        : showBossesAndElites ? RespawnTimerScope.BossesAndElites
        : RespawnTimerScope.None;

    /// <summary>
    /// A spawn point counts as a boss or elite spawn when its common or rare
    /// spawn table holds one, so a rare elite's timer shows even after a common
    /// creature took the spawn.
    /// </summary>
    public static bool Shows(RespawnTimerScope scope, bool spawnsBossOrElite) =>
        scope == RespawnTimerScope.All
        || (scope == RespawnTimerScope.BossesAndElites && spawnsBossOrElite);
}
