namespace InteractiveMapCompanion;

/// <summary>
/// The interactive map that the overlay shows and that pairing links open.
/// </summary>
internal static class MapSite
{
    internal const string MapUrl = "https://erenshor.compendiums.org/map";

    /// <summary>
    /// The overlay runs inside the game, so it opens the map with Live on.
    /// </summary>
    internal const string OverlayUrl = MapUrl + "?live=1";
}
