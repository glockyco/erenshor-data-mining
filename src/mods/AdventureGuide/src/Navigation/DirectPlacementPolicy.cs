namespace AdventureGuide.Navigation;

/// <summary>Matches live characters to exported direct placements.</summary>
internal static class DirectPlacementPolicy
{
    /// <summary>Squared distance within which a live NPC is at an exported placement.</summary>
    /// <remarks>
    /// Exported coordinates are rounded to centimetres. A 2 m tolerance
    /// allows drift while distinguishing props placed 3 m apart.
    /// </remarks>
    private const float MaxDriftSqr = 4f;

    public static bool IsSamePlacement(float squaredDistance) => squaredDistance <= MaxDriftSqr;
}
