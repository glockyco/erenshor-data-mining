namespace AdventureGuide.State;

/// <summary>
/// Reads the same authoritative canvas reference the game toggles for F7.
/// </summary>
internal static class GameUIVisibility
{
    public static bool IsVisible => GameData.MainCanvas?.enabled ?? true;
}
