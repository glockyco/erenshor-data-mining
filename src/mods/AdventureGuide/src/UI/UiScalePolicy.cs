namespace AdventureGuide.UI;

internal static class UiScalePolicy
{
    public static float Normalize(float value) =>
        value == -1f || float.IsNaN(value) ? -1f : Math.Max(0.5f, Math.Min(4f, value));
}
