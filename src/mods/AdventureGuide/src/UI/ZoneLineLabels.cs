namespace AdventureGuide.UI;

internal static class ZoneLineLabels
{
    public static string Selectable(string destination, float distance, int stepOrder, int index) =>
        $"To {destination} ({distance:F0}m)###zl_{stepOrder}_{index}";
}
