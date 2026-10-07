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

    // Source coordinates are rounded to two decimal places in the guide.
    public static bool MatchesNode(float squaredDistance) => squaredDistance <= 0.01f;
}
