namespace AdventureGuide.State;

internal static class InventoryCountPolicy
{
    // Quantity is a stack count for General items, but a quality tier for gear.
    internal static void Add(
        Dictionary<string, int> counts,
        string key,
        bool isGeneral,
        int quantity
    )
    {
        int contribution = isGeneral ? quantity : 1;
        counts[key] = counts.TryGetValue(key, out int count) ? count + contribution : contribution;
    }
}
