namespace AdventureGuide.Navigation;

internal static class MarkerFadePolicy
{
    internal static float SubTextAlpha(float distance) =>
        distance >= 80f ? 0f
        : distance > 60f ? (80f - distance) / 20f
        : 1f;

    internal static bool ShouldRefreshSubText(float distance, int currentValue, int shownValue) =>
        SubTextAlpha(distance) > 0f && currentValue != shownValue;
}
