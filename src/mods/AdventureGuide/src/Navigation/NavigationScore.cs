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
        const float NonActionablePenalty = 500_000f;

        float dx = sel.Target.X - playerX;
        float dy = sel.Target.Y - playerY;
        float dz = sel.Target.Z - playerZ;
        float dist2 = dx * dx + dy * dy + dz * dz;

        float penalty = 0f;
        if (!sel.IsSameZone)
            penalty += CrossZonePenalty;
        if (!sel.Target.IsActionable)
            penalty += NonActionablePenalty;
        return dist2 + penalty;
    }
}
