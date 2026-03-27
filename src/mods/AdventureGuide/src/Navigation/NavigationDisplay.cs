namespace AdventureGuide.Navigation;

/// <summary>
/// Rendering constants shared across navigation overlay components.
/// </summary>
internal static class NavigationDisplay
{
    /// <summary>
    /// Height above the NavMesh surface (in world units) at which navigation
    /// indicators render. Applied uniformly to all points — interior path
    /// corners, player endpoint, and target endpoint — so the path and arrow
    /// diamond remain visually consistent with each other.
    /// </summary>
    internal const float GroundOffset = 0.50f;
}
