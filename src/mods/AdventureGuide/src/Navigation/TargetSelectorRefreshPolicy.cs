namespace AdventureGuide.Navigation;

/// <summary>
/// Decides when the shared navigation target selector must rebuild its target
/// lists from the current navigation-target source.
///
/// Any meaningful live-world change forces a rebuild, even if the source
/// version did not advance. That keeps NAV aligned with mined nodes,
/// despawned corpses, and other transient state changes that can change target
/// actionability without changing the selected quest set.
/// </summary>
internal static class TargetSelectorRefreshPolicy
{
    public static bool ShouldForce(
        bool liveWorldChanged,
        int targetSourceVersion,
        int lastTargetSourceVersion,
        int navSetVersion,
        int lastNavSetVersion)
    {
        return liveWorldChanged
            || targetSourceVersion != lastTargetSourceVersion
            || navSetVersion != lastNavSetVersion;
    }
}
