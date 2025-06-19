#nullable enable

using SQLite;

[Table("LootDrops")]
public class LootTableDBRecord
{
    [Indexed(Name = "LootDrops_Primary_IDX", Order = 1, Unique = true)]
    public string CharacterPrefabGuid { get; set; } = string.Empty;

    [Indexed(Name = "LootDrops_Primary_IDX", Order = 2, Unique = true)]
    public string ItemId { get; set; } = string.Empty;

    // Probability that this item drops at least once per kill
    public double DropProbability { get; set; }

    // Expected number of this item per kill
    public double ExpectedPerKill { get; set; }

    // JSON-serialized array of per-kill DropCountProbabilities, e.g. [0.7,0.25,0.05]
    public string DropCountDistribution { get; set; } = string.Empty;

    public bool IsGuaranteed { get; set; }
    public bool IsUnique { get; set; }
    public bool IsVisible { get; set; }
}