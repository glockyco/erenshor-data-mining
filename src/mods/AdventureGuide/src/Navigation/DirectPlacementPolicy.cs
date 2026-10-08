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
    /// <summary>Squared distance within which a live NPC is at an exported placement.</summary>
    /// <remarks>
    /// Observed drift is under 0.25 m and exported coordinates are rounded to
    /// centimetres; 2 m is generous yet tells apart props placed 3 m apart.
    /// </remarks>
    private const float MaxDriftSqr = 4f;

    public static bool IsSamePlacement(float squaredDistance) => squaredDistance <= MaxDriftSqr;

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
