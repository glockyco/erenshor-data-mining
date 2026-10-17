using System.Globalization;
using AdventureGuide.Data;

namespace AdventureGuide.UI;

/// <summary>Source text is formatted when presentation caches change, not during drawing.</summary>
internal static class SourceListText
{
    public static string Summary(ItemSource source)
    {
        string action = source.Type switch
        {
            "drop" => $"Defeat {source.Name}",
            "world_drop" or "common_world_item" => source.Name ?? "World drops",
            "fishing_bonus" => $"Fishing: {source.Name}",
            "treasure_chest" => "Open a treasure map chest",
            "vendor" => $"Buy from {source.Name}",
            "dialog_give" => source.Keyword is { Length: > 0 }
                ? $"Say \"{source.Keyword}\" to {source.Name}"
                : $"Talk to {source.Name}",
            "fishing" => "Fish",
            "mining" => "Mine",
            "pickup" => source.Name == null ? "Find in the world" : $"Find {source.Name}",
            "crafting" => $"Craft {source.Name}",
            "quest_reward" => $"Quest reward: {source.Name}",
            "ingredient" => $"Ingredient: {source.Name}"
                + (source.NodeCount is int qty ? $" x{qty}" : ""),
            "item_use" => $"Use {source.Name}",
            _ => source.Name ?? source.Type,
        };
        string? zone = source.Zone ?? source.Scene;
        string text =
            zone == null ? action
            : source.Type is "fishing" or "mining" ? $"{action} in {zone}"
            : $"{action}  ·  {zone}";
        return AreaLabel(source) is string level ? $"{text} ({level})" : text;
    }

    public static string? AreaLabel(ItemSource source)
    {
        if (ItemSourcePolicy.IsRandomSource(source) || source.Level is not int level)
            return null;
        return source.Type is "fishing" or "mining" ? $"Area Lv {level}"
            : source.Type is "drop" or "vendor" or "dialog_give" ? $"NPC Lv {level}"
            : $"Lv {level}";
    }

    public static string? OptionOdds(ItemSource source)
    {
        if (source.Type == "fishing")
        {
            if (source.TimeRestriction == "day")
                return $"Day only · {Percent(source.DayChance!.Value)}";
            if (source.TimeRestriction == "night")
                return $"Night only · {Percent(source.NightChance!.Value)}";
            return source.DayChance == source.NightChance
                ? Percent(source.DayChance!.Value)
                : $"Day {Percent(source.DayChance!.Value)} / night {Percent(source.NightChance!.Value)}";
        }
        if (source.Chance is not double chance)
            return null;
        return source.ChanceMax is double maximum && maximum != chance
            ? $"{Percent(chance)} to {Percent(maximum)}"
            : Percent(chance);
    }

    public static string Details(ItemSource source)
    {
        string text = Summary(source);
        if (source.Type == "fishing")
        {
            if (source.TimeRestriction == "day")
                text +=
                    "\nDay only (06:00-21:59): "
                    + Percent(source.DayChance!.Value)
                    + " per successful catch.";
            else if (source.TimeRestriction == "night")
                text +=
                    "\nNight only (22:00-05:59): "
                    + Percent(source.NightChance!.Value)
                    + " per successful catch.";
            else if (source.DayChance == source.NightChance)
                text +=
                    "\nDay and night: "
                    + Percent(source.DayChance!.Value)
                    + " per successful catch.";
            else
                text +=
                    "\nDay (06:00-21:59): "
                    + Percent(source.DayChance!.Value)
                    + ", night (22:00-05:59): "
                    + Percent(source.NightChance!.Value)
                    + " per successful catch.";
        }
        else if (source.Chance is double chance)
        {
            text += "\nChance: " + Percent(chance);
            if (source.ChanceMax is double maximum && maximum != chance)
                text += " to " + Percent(maximum);
        }
        if (source.Type == "treasure_chest")
            text += $"\nDig at Lv {source.Level}-{source.LevelMax}.";
        if (!string.IsNullOrWhiteSpace(source.Instruction))
            text += "\n" + source.Instruction;
        return text;
    }

    private static string Percent(double chance) =>
        chance > 0 && chance < 0.01
            ? "<0.01%"
            : chance.ToString("0.##", CultureInfo.InvariantCulture) + "%";

    /// <summary>Phase changes select literal text without rebuilding source labels.</summary>
    public static string? Timing(ItemSource? source, int hour)
    {
        if (source?.Type != "fishing")
            return null;
        bool available = ItemSourcePolicy.FishingChance(source, hour) > 0;
        return source.TimeRestriction == "day"
            ? available
                ? "Fish during the day (06:00-21:59)."
                : "Return during the day (06:00-21:59)."
            : source.TimeRestriction == "night"
                ? available
                    ? "Fish at night (22:00-05:59)."
                    : "Return at night (22:00-05:59)."
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
