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
                    (step.RequirementVariant == null || item.VariantKey == step.RequirementVariant)
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

    public static IReadOnlyList<SourceChoice> PresentationSources(List<ItemSource> sources)
    {
        var choices = SourceChoice.ForSources(sources);
        bool hasInputs = false;
        foreach (var source in sources)
            if (source.Type == "ingredient" && source.CanonicalUse?.Kind == "crafting_material")
            {
                hasInputs = true;
                break;
            }
        if (!hasInputs)
            return choices;
        var rows = new List<SourceChoice>(choices.Count);
        foreach (var choice in choices)
        {
            int matching = -1;
            for (int i = 0; i < rows.Count; i++)
                if (SameMaterialInput(rows[i].Primary, choice.Primary))
                {
                    matching = i;
                    break;
                }
            // The last slot carries the cumulative threshold. Keep the original
            // choices and native use records intact for requirement resolution.
            if (matching >= 0)
                rows[matching] = choice;
            else
                rows.Add(choice);
        }
        return rows;
    }

    private static bool SameMaterialInput(ItemSource a, ItemSource b)
    {
        var x = a.CanonicalUse;
        var y = b.CanonicalUse;
        if (
            a.Type != "ingredient"
            || b.Type != "ingredient"
            || a.ItemStableKey == null
            || a.ItemStableKey != b.ItemStableKey
            || a.OutputQuality != b.OutputQuality
            || a.Condition != b.Condition
            || x == null
            || y == null
            || x.Kind != "crafting_material"
            || y.Kind != x.Kind
            || x.TargetStableKey == null
            || x.TargetStableKey != y.TargetStableKey
            || x.VariantKey != y.VariantKey
            || x.Conditions.Count != 0
            || y.Conditions.Count != 0
            || x.Locations.Count != 0
            || y.Locations.Count != 0
        )
            return false;
        return SameInputSources(a.Children, b.Children);
    }

    private static bool SameInputSources(List<ItemSource>? a, List<ItemSource>? b)
    {
        if (ReferenceEquals(a, b))
            return true;
        if ((a?.Count ?? 0) != (b?.Count ?? 0))
            return false;
        if (a == null || b == null)
            return true;
        for (int i = 0; i < a.Count; i++)
        {
            var left = a[i];
            var right = b[i];
            if (
                left.MakeSourceId() != right.MakeSourceId()
                || left.Condition != right.Condition
                || left.Quantity != right.Quantity
                || left.OutputQuality != right.OutputQuality
                || !SameInputSources(left.Children, right.Children)
            )
                return false;
        }
        return true;
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
