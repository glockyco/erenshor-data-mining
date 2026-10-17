#nullable enable

using SQLite;

[Table("LootTableSources")]
public class LootTableSourceRecord
{
    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string? CharacterStableKey { get; set; }

    [ForeignKey(typeof(MiningNodeRecord), "StableKey")]
    public string? MiningNodeStableKey { get; set; }

    public int ComponentIndex { get; set; }
    public bool ComponentIsEnabled { get; set; }
    public int MaxNumberDrops { get; set; }
    public int MaxNonCommonDrops { get; set; }
    public int NumberOfGuaranteedDrops { get; set; }
    public int? UltraRareDropCount { get; set; }
    public int? LegendaryDropCount { get; set; }
    public int? RareDropCount { get; set; }
    public int? UncommonDropCount { get; set; }
    public int? CommonDropCount { get; set; }
    public int? GuaranteeOneDropCount { get; set; }
    public int? ActualDropsCount { get; set; }
}

[Table("LootTablePoolSlots")]
public class LootTablePoolSlotRecord
{
    [Indexed(Name = "LootTablePoolSlots_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(LootTableSourceRecord), "StableKey")]
    public string LootTableStableKey { get; set; } = string.Empty;

    [Indexed(Name = "LootTablePoolSlots_Primary_IDX", Order = 2, Unique = true)]
    public string Pool { get; set; } = string.Empty;

    [Indexed(Name = "LootTablePoolSlots_Primary_IDX", Order = 3, Unique = true)]
    public int Position { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
}
