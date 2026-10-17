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
                    item.VariantKey == step.RequirementVariant
                    && item.OutputQuality == step.OutputQuality
                    && (
                        step.TargetKey != null
                            ? item.ItemStableKey == step.TargetKey
                            : string.Equals(
                                item.ItemName,
                                step.TargetName,
                                StringComparison.OrdinalIgnoreCase
                            )
                    )
                )
                    return item.Sources;
        return null;
    }

    public static bool IsRandomSource(ItemSource source) =>
        source.Type is "world_drop" or "common_world_item" or "fishing_bonus" or "treasure_chest";

    public static bool IsStaticCandidate(ItemSource source) =>
        !IsRandomSource(source)
        && source.Type != "item_use"
        && source.Type != "quest_reward"
        && source.Type != "ingredient";

    // Water.Update uses a different window from night-only NPC spawns.
    public static bool IsFishingDay(int hour) => hour > 5 && hour < 22;

    public static double? FishingChance(ItemSource source, int hour) =>
        IsFishingDay(hour) ? source.DayChance : source.NightChance;

    public static bool NeedsUsedItem(
        ItemSource source,
        Func<string, int>? countItem,
        List<ItemSource>? siblings = null
    )
    {
        if (countItem == null)
            return true;
        if (source.Type == "ingredient" && source.ItemStableKey != null)
            return countItem(source.ItemStableKey) < RequiredInputQuantity(source, siblings);
        return source.Type != "item_use"
            || source.SourceKey == null
            || countItem(source.SourceKey) == 0;
    }

    public static double RequiredInputQuantity(ItemSource source, List<ItemSource>? siblings)
    {
        if (siblings == null)
            return source.Quantity ?? 1;
        double required = 0;
        foreach (var input in siblings)
        {
            if (input.Type == "ingredient" && input.ItemStableKey == source.ItemStableKey)
                required += input.Quantity ?? 1;
            if (ReferenceEquals(input, source))
                break;
        }
        return required;
    }

    public static bool HasPendingChildren(ItemSource source, Func<string, int>? countItem)
    {
        if (source.Children == null)
            return false;
        foreach (var child in source.Children)
            if (NeedsUsedItem(child, countItem, source.Children))
                return true;
        return false;
    }

    public static string? SceneOf(ItemSource source) =>
        source.AcquisitionKey != null ? source.CanonicalLocation?.Scene : source.Scene;

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
            if (!NeedsUsedItem(source, countItem, sources))
                continue;
            if (source.Type == "item_use" && source.Name != null)
                output.Add(source.Name);
            AddUsedItems(source.Children, countItem, output);
        }
    }
}
