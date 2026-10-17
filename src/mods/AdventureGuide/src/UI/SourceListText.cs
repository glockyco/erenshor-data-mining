using System.Globalization;
using AdventureGuide.Data;

namespace AdventureGuide.UI;

/// <summary>Source text is formatted when presentation caches change, not during drawing.</summary>
internal static class SourceListText
{
    public static string Action(
        ItemSource source,
        string? itemName = null,
        double? inputQuantity = null
    )
    {
        string action = ActionText(source, itemName, inputQuantity);
        return source.Type != "fishing" && OptionOdds(source) is string odds
            ? $"{action} ({odds})"
            : action;
    }

    public static bool RepeatsAction(ItemSource source, string instruction)
    {
        string action = ActionText(source);
        return string.Equals(instruction, action, StringComparison.Ordinal)
            || (
                instruction.Length == action.Length + 1
                && instruction[instruction.Length - 1] == '.'
                && instruction.StartsWith(action, StringComparison.Ordinal)
            );
    }

    private static string ActionText(
        ItemSource source,
        string? itemName = null,
        double? inputQuantity = null
    ) =>
        source.Type switch
        {
            "drop" => $"Defeat {source.Name}",
            "world_drop" or "common_world_item" => source.Name ?? "World drops",
            "fishing_bonus" => $"Fishing: {source.Name}",
            "treasure_chest" => "Open a treasure map chest",
            "vendor" => $"Buy from {source.Name}",
            "dialog_give" => source.Keyword is { Length: > 0 }
                ? $"Say \"{source.Keyword}\" to {source.Name}"
                : $"Talk to {source.Name}",
            "fishing" => itemName == null ? "Fish" : $"Fish for {itemName}",
            "mining" => itemName == null ? "Mine" : $"Mine {itemName}",
            "pickup" => source.Name == null ? "Find in the world" : $"Find {source.Name}",
            "crafting" => $"Craft using {source.Name}",
            "quest_reward" => $"Quest reward: {source.Name}",
            "ingredient" => $"Ingredient: {source.Name}"
                + (
                    (inputQuantity ?? source.Quantity ?? source.NodeCount) is double qty && qty > 1
                        ? $" x{qty.ToString("0.##", CultureInfo.InvariantCulture)}"
                        : ""
                ),
            "item_use" => $"Use {source.Name}",
            _ => source.Name ?? source.Type,
        };

    public static string? Location(ItemSource source)
    {
        string? zone = source.Zone ?? source.Scene;
        string? level = AreaLabel(source);
        string? location =
            zone == null ? level
            : level == null ? zone
            : $"{zone} · {level}";
        string? slot = RoomSlot(source);
        return slot == null ? location
            : location == null ? $"Room {slot}"
            : $"{location} · Room {slot}";
    }

    private static string? RoomSlot(ItemSource source)
    {
        if (source.CanonicalLocation == null)
            return null;
        string? slot = null;
        foreach (var condition in source.CanonicalLocation.Conditions)
        {
            if (condition.Phase != "availability" || condition.Predicate != "room_furnished")
                continue;
            if (slot != null && slot != condition.ReferenceSlot)
                return null;
            slot = condition.ReferenceSlot;
        }
        return slot;
    }

    public static string? AreaLabel(ItemSource source)
    {
        if (ItemSourcePolicy.IsRandomSource(source) || source.Level is not int level)
            return null;
        return source.Type is "fishing" or "mining" ? $"Area Lv{level}"
            : source.Type is "drop" or "vendor" or "dialog_give" ? $"NPC Lv{level}"
            : $"Lv{level}";
    }

    public static string? OptionOdds(ItemSource source)
    {
        if (source.Type == "fishing")
        {
            if (source.TimeRestriction == "day")
                return $"Day only (06:00-21:59) · {Percent(source.DayChance!.Value)} per successful catch";
            if (source.TimeRestriction == "night")
                return $"Night only (22:00-05:59) · {Percent(source.NightChance!.Value)} per successful catch";
            return source.DayChance == source.NightChance
                ? $"{Percent(source.DayChance!.Value)} per successful catch"
                : $"Day {Percent(source.DayChance!.Value)} / night {Percent(source.NightChance!.Value)} per successful catch";
        }
        if (source.Chance is not double chance)
            return null;
        string odds =
            source.ChanceMax is double maximum && maximum != chance
                ? $"{Percent(chance)} to {Percent(maximum)}"
                : Percent(chance);
        return source.Type == "treasure_chest"
            ? $"{odds} · Dig at Lv {source.Level}-{source.LevelMax}"
            : odds;
    }

    private static string Percent(double chance) =>
        chance > 0 && chance < 0.01
            ? "<0.01%"
            : chance.ToString("0.##", CultureInfo.InvariantCulture) + "%";

    /// <summary>Phase changes select literal text without rebuilding source labels.</summary>
    public static string? Timing(ItemSource? source, int hour)
    {
        if (source?.Type != "fishing" || ItemSourcePolicy.FishingChance(source, hour) > 0)
            return null;
        return source.TimeRestriction == "day" ? "Wait for day."
            : source.TimeRestriction == "night" ? "Wait for night."
            : null;
    }

    public static string FishingStatus(ItemSource source, int hour) =>
        ItemSourcePolicy.FishingChance(source, hour) == 0
            ? source.TimeRestriction == "day"
                ? "Fishing: wait for day"
                : "Fishing: wait for night"
            : source.TimeRestriction == "day"
                ? "Fishing: day only"
                : source.TimeRestriction == "night"
                    ? "Fishing: night only"
                    : "Fishing";
}
