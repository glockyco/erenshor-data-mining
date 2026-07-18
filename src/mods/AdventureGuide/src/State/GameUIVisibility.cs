namespace AdventureGuide.State;

/// <summary>
/// Reads the same authoritative canvas reference the game toggles for F7.
/// </summary>
internal static class GameUIVisibility
{
    public static bool IsVisible
    {
        get
        {
            // GameData.MainCanvas can hold a destroyed Canvas during scene
            // transitions. `?.` only checks the managed reference, so the
            // `.enabled` access throws. Unity's overloaded null check covers
            // both the unassigned and the destroyed case.
            var canvas = GameData.MainCanvas;
            return canvas == null || canvas.enabled;
        }
    }
}
