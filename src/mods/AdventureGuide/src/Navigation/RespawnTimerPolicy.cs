namespace AdventureGuide.Navigation;

/// <summary>Named encounters a spawn point's common or rare spawn table holds.</summary>
[System.Flags]
internal enum SpawnTiers
{
    None = 0,
    Boss = 1,
    Elite = 2,
}

internal static class RespawnTimerPolicy
{
    /// <summary>
    /// Whether a spawn point without a quest target shows its respawn timer.
    /// ShowAllRespawnTimers includes boss and elite spawn points. A rare boss
    /// or elite counts, so its timer shows even after a common creature took
    /// the spawn.
    /// </summary>
    public static bool Shows(bool showAll, bool showBosses, bool showElites, SpawnTiers tiers) =>
        showAll
        || (showBosses && (tiers & SpawnTiers.Boss) != 0)
        || (showElites && (tiers & SpawnTiers.Elite) != 0);
}
