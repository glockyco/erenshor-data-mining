#nullable enable

using SQLite;

[Table("LootDrops")]
public class LootTableRecord
{
    public const string TableName = "LootDrops";

    [Indexed(Name = "LootDrops_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "LootDrops_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string ItemStableKey { get; set; } = string.Empty;

    // Probability that this item drops at least once per kill
    public double DropProbability { get; set; }

    // Expected number of this item per kill
    public double ExpectedPerKill { get; set; }

    // JSON-serialized array of per-kill DropCountProbabilities, e.g. [0.7,0.25,0.05]
    public string DropCountDistribution { get; set; } = string.Empty;

    public bool IsActual { get; set; }
    public bool IsGuaranteed { get; set; }
    public bool IsCommon { get; set; }
    public bool IsUncommon { get; set; }
    public bool IsRare { get; set; }
    public bool IsLegendary { get; set; }
    public bool IsUltraRare { get; set; }
    public bool IsUnique { get; set; }
    public bool IsVisible { get; set; }
    public string Zone { get; set; } = string.Empty;
}