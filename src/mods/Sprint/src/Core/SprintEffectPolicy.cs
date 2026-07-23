namespace Sprint.Core;

/// <summary>Calculates the run speed produced by Sprint's stat policy.</summary>
internal static class SprintEffectPolicy
{
    private const float MinimumRunSpeed = 2f;

    /// <summary>
    /// Combines base and status-effect run speed, applying the configured
    /// multiplier only while Sprint is active, then enforces the game's minimum.
    /// </summary>
    internal static float CalculateActualRunSpeed(
        float baseRunSpeed,
        float statusEffectRunSpeed,
        bool active,
        float multiplier
    )
    {
        float runSpeed = baseRunSpeed + statusEffectRunSpeed;
        if (active)
            runSpeed *= multiplier;

        return runSpeed < MinimumRunSpeed ? MinimumRunSpeed : runSpeed;
    }
}
