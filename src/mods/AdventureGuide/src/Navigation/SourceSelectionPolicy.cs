namespace AdventureGuide.Navigation;

/// <summary>Unmined sources beat mined nodes; exhausted nodes use respawn order.</summary>
public static class SourceSelectionPolicy
{
    public static bool ShouldConsiderCharacter(bool preferLiveCharacters, bool hasLiveNpc) =>
        !preferLiveCharacters || hasLiveNpc;

    public static bool IsBetter(
        bool mined,
        float distance,
        float respawn,
        bool bestMined,
        float bestDistance,
        float bestRespawn
    )
    {
        if (mined != bestMined)
            return !mined;
        if (mined && respawn != bestRespawn)
            return respawn < bestRespawn;
        return distance < bestDistance;
    }

    /// <summary>
    /// Among sources in other scenes, prefer the scene with an open route over
    /// a locked one, then the fewest zone crossings. Scenes without any route
    /// rank last. Equal sources keep the guide's source order.
    /// </summary>
    public static bool IsBetterCrossZone(
        bool routable,
        bool locked,
        int hops,
        bool bestRoutable,
        bool bestLocked,
        int bestHops
    )
    {
        if (routable != bestRoutable)
            return routable;
        if (locked != bestLocked)
            return !locked;
        return hops < bestHops;
    }

    // Source coordinates are rounded to two decimal places in the guide.
    public static bool MatchesNode(float squaredDistance) => squaredDistance <= 0.01f;
}
