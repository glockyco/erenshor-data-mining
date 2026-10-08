using System.Globalization;
using AdventureGuide.Data;

namespace AdventureGuide.UI;

/// <summary>Text for the collapsed tail of a step's item source list.</summary>
internal static class SourceListText
{
    /// <summary>Formatted once when the detail panel's display cache changes.</summary>
    public static string Label(ItemSource source)
    {
        string label = source.Type switch
        {
            "world_drop" => $"Drops from: {source.Name}",
            "fishing_bonus" => $"Fishing: {source.Name}",
            "treasure_chest" => $"Treasure map chest (dig at Lv {source.Level}-{source.LevelMax})",
            "drop" => $"Drops from: {source.Name}",
            "vendor" when !string.IsNullOrWhiteSpace(source.Instruction) =>
                $"{source.Instruction}  ·  {source.Name}",
            "vendor" => $"Buy from: {source.Name}",
            "dialog_give" => $"Given by: {source.Name}",
            "fishing" => "Fishing",
            "mining" => "Mining",
            "pickup" => source.Name == null ? "Found in world" : $"Found in world: {source.Name}",
            "crafting" => $"Crafted from: {source.Name}",
            "quest_reward" => $"Quest reward: {source.Name}",
            "ingredient" => $"Ingredient: {source.Name}"
                + (source.NodeCount is int qty ? $" x{qty}" : ""),
            "item_use" => $"Use: {source.Name}",
            _ => source.Name ?? source.Type,
        };
        if (source.Zone != null)
            label += $"  ·  {source.Zone}";
        if (!ItemSourcePolicy.IsRandomSource(source) && source.Level is int level)
            label += $"  ·  Lv {level}";
        if (source.Chance is double chance)
            label +=
                "  ·  "
                + chance.ToString(
                    source.Type == "treasure_chest" ? "0" : "0.###",
                    CultureInfo.InvariantCulture
                )
                + "%";
        return label;
    }

    /// <summary>
    /// "N more sources (Lv a-b)" for the sources from <paramref name="start"/>
    /// on. Random bonus and treasure sources do not imply a recommended level.
    /// </summary>
    public static string MoreSources(IReadOnlyList<ItemSource> sources, int start)
    {
        int? min = null;
        int? max = null;
        for (int i = start; i < sources.Count; i++)
        {
            if (ItemSourcePolicy.IsRandomSource(sources[i]) || sources[i].Level is not int level)
                continue;
            if (min == null || level < min)
                min = level;
            if (max == null || level > max)
                max = level;
        }

        int remaining = sources.Count - start;
        if (min == null)
            return $"{remaining} more sources";
        return min == max
            ? $"{remaining} more sources (Lv {min})"
            : $"{remaining} more sources (Lv {min}-{max})";
    }
}
