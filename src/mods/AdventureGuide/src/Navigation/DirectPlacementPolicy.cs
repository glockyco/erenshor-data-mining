namespace AdventureGuide.Navigation;

/// <summary>Resolved state of a directly-placed spawn's quest gate.</summary>
internal enum DirectPlacementGateState
{
    Absent,
    Unresolved,
    Incomplete,
    Completed,
}

/// <summary>
/// Decides whether a missing directly-placed NPC may advertise a zone-reentry
/// respawn marker. Inputs are already resolved by the game-facing coordinator;
/// keeping this policy free of GuideData, quest state, and Unity makes every
/// precedence boundary testable without a loader or game installation.
/// </summary>
internal static class DirectPlacementPolicy
{
    public static bool ShouldSuppressRespawn(
        bool characterUnlockIsAmbiguous,
        bool hasSourceScript,
        DirectPlacementGateState gateState
    )
    {
        if (characterUnlockIsAmbiguous || hasSourceScript)
            return true;

        return gateState
            is DirectPlacementGateState.Unresolved
                or DirectPlacementGateState.Incomplete;
    }
}
