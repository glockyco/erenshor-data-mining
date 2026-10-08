namespace AdventureGuide.Data;

/// <summary>Sources without fixed locations never enter static spawn resolution.</summary>
internal static class ItemSourcePolicy
{
    public static List<ItemSource>? SourcesFor(QuestEntry quest, QuestStep step)
    {
        if (step.Sources != null)
            return step.Sources;
        if (quest.RequiredItems != null)
            foreach (var item in quest.RequiredItems)
                if (
                    item.ItemStableKey == step.TargetKey
                    || string.Equals(
                        item.ItemName,
                        step.TargetName,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                    return item.Sources;
        return null;
    }

    public static bool IsRandomSource(ItemSource source) =>
        source.Type is "world_drop" or "fishing_bonus" or "treasure_chest";

    public static bool IsStaticCandidate(ItemSource source) =>
        !IsRandomSource(source) && source.Type is not "item_use" and not "quest_reward";

    public static bool NeedsUsedItem(ItemSource source, Func<string, int>? countItem) =>
        source.Type != "item_use"
        || source.SourceKey == null
        || countItem == null
        || countItem(source.SourceKey) == 0;

    public static void AddUsedItems(
        List<ItemSource>? sources,
        Func<string, int> countItem,
        HashSet<string> output
    )
    {
        if (sources == null)
            return;
        foreach (var source in sources)
        {
            if (!NeedsUsedItem(source, countItem))
                continue;
            if (source.Type == "item_use" && source.Name != null)
                output.Add(source.Name);
            AddUsedItems(source.Children, countItem, output);
        }
    }
}
