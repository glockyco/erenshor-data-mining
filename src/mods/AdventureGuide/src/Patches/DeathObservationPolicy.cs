namespace AdventureGuide.Patches;

internal static class DeathObservationPolicy
{
    // Undying and Universal Will return from DoDeath with Alive still true.
    internal static bool ShouldObserve(bool aliveAfterDoDeath) => !aliveAfterDoDeath;
}
