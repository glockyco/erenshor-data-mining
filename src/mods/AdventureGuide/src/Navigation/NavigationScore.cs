namespace AdventureGuide.Navigation;

internal static class NavigationScore
{
    internal static float Compute(
        SelectedNavTarget sel,
        float playerX,
        float playerY,
        float playerZ
    )
    {
        const float CrossZonePenalty = 1_000_000f;
        const float SameZoneNonActionablePenalty = 500_000f;
        const float CrossZoneUnreachablePenalty = float.MaxValue / 4f;
        const float CrossZoneHopPenalty = 10_000f;
        const float CrossZoneNonActionablePenalty = 1_000f;

        if (sel.IsSameZone)
        {
            float dx = sel.Target.X - playerX;
            float dy = sel.Target.Y - playerY;
            float dz = sel.Target.Z - playerZ;
            float dist2 = dx * dx + dy * dy + dz * dz;
            return dist2 + (sel.Target.IsActionable ? 0f : SameZoneNonActionablePenalty);
        }

        float hopScore = sel.HopCount < 0
            ? CrossZoneUnreachablePenalty
            : sel.HopCount * CrossZoneHopPenalty;
        float actionScore = sel.Target.IsActionable ? 0f : CrossZoneNonActionablePenalty;
        return CrossZonePenalty + hopScore + actionScore;
    }
}
