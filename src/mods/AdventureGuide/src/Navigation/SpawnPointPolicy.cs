namespace AdventureGuide.Navigation;

/// <summary>Respawn phase of one live SpawnPoint, as the game's spawn rules decide it.</summary>
internal enum SpawnPointPhase
{
    /// <summary>The NPC the caller looks for is alive at the point.</summary>
    TargetAlive,

    /// <summary>A different NPC from the point's spawn table is alive.</summary>
    OtherAlive,

    /// <summary>
    /// The point cannot spawn: a quest gate or an encounter script cleared
    /// <c>canSpawn</c>, or a completed StopIfQuestComplete quest ended it.
    /// </summary>
    Withheld,

    /// <summary>A night-only point outside the 23:00-03:59 spawn window.</summary>
    NightLocked,

    /// <summary>
    /// The zone load is still populating the point: nothing spawned or died
    /// there during this visit, and the player did not leave it respawning.
    /// </summary>
    Populating,

    /// <summary>The point's NPC died or despawned, and its respawn timer runs.</summary>
    Respawning,
}

/// <summary>Live SpawnPoint state that decides its respawn phase.</summary>
internal readonly struct SpawnPointFacts
{
    public readonly bool AnyAlive;
    public readonly bool TargetAlive;
    public readonly bool CanSpawn;
    public readonly bool StopQuestCompleted;
    public readonly bool NightSpawn;
    public readonly int Hour;
    public readonly bool HasRespawnHistory;

    public SpawnPointFacts(
        bool anyAlive,
        bool targetAlive,
        bool canSpawn,
        bool stopQuestCompleted,
        bool nightSpawn,
        int hour,
        bool hasRespawnHistory
    )
    {
        AnyAlive = anyAlive;
        TargetAlive = targetAlive;
        CanSpawn = canSpawn;
        StopQuestCompleted = stopQuestCompleted;
        NightSpawn = nightSpawn;
        Hour = hour;
        HasRespawnHistory = hasRespawnHistory;
    }
}

/// <summary>
/// Mirrors SpawnPoint.Update without Unity so every precedence boundary is
/// testable. A live NPC wins over every spawn rule: encounter scripts clear
/// <c>canSpawn</c> while their boss fights. A stop quest only takes effect
/// when the timer expires, but the point never spawns again either way.
/// </summary>
internal static class SpawnPointPolicy
{
    /// <summary>
    /// SpawnPoint.Update spawns a night-only NPC only after 22:59 and before
    /// 04:00. It despawns a living one from 07:00 until 22:59.
    /// </summary>
    public static bool IsNightSpawnHour(int hour) => hour > 22 || hour < 4;

    public static SpawnPointPhase Classify(in SpawnPointFacts facts)
    {
        if (facts.AnyAlive)
            return facts.TargetAlive ? SpawnPointPhase.TargetAlive : SpawnPointPhase.OtherAlive;
        if (!facts.CanSpawn || facts.StopQuestCompleted)
            return SpawnPointPhase.Withheld;
        if (facts.NightSpawn && !IsNightSpawnHour(facts.Hour))
            return SpawnPointPhase.NightLocked;
        return facts.HasRespawnHistory ? SpawnPointPhase.Respawning : SpawnPointPhase.Populating;
    }
}
