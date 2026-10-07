namespace AdventureGuide.UI;

internal static class TrackerVisibilityPolicy
{
    public static bool ShouldDraw(bool userVisible, bool inGameplay, bool enabled) =>
        userVisible && inGameplay && enabled;
}
