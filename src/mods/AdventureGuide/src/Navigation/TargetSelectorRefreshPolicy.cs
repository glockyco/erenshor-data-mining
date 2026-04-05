namespace AdventureGuide.Navigation;

/// <summary>
/// Decides when the shared navigation target selector must rebuild its target
/// lists from the resolution service.
///
/// Any meaningful live-world change forces a rebuild, even if the resolution
/// cache version did not advance. That keeps NAV aligned with mined nodes,
/// despawned corpses, and other transient state changes that can change target
/// actionability without changing the selected quest set.
/// </summary>
internal static class TargetSelectorRefreshPolicy
{
    public static bool ShouldForce(
        bool liveWorldChanged,
        int resolutionVersion,
        int lastResolutionVersion,
        int navSetVersion,
        int lastNavSetVersion)
    {
        return liveWorldChanged
            || resolutionVersion != lastResolutionVersion
            || navSetVersion != lastNavSetVersion;
    }
}
