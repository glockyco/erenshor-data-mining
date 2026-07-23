namespace Sprint.Core;

/// <summary>Determines whether Sprint may affect a game object.</summary>
internal static class SprintEligibility
{
    /// <summary>
    /// Returns true only when <paramref name="candidate"/> is the non-null
    /// player reference. Equality overrides are intentionally ignored.
    /// </summary>
    internal static bool IsPlayer<T>(T? player, T candidate)
        where T : class => player is not null && ReferenceEquals(player, candidate);

    /// <summary>
    /// Returns true only for the started, active player instance.
    /// </summary>
    internal static bool IsActiveFor<T>(bool started, bool active, T? player, T candidate)
        where T : class => started && active && IsPlayer(player, candidate);
}
