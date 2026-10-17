#nullable enable

using SQLite;

[Table("MiningNodePoolSlots")]
public class MiningNodePoolSlotRecord
{
    public const string TableName = "MiningNodePoolSlots";

    [Indexed(Name = "MiningNodePoolSlots_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(MiningNodeRecord), "StableKey")]
    public string MiningNodeStableKey { get; set; } = string.Empty;

    [Indexed(Name = "MiningNodePoolSlots_Primary_IDX", Order = 2, Unique = true)]
    public string Pool { get; set; } = string.Empty;

    [Indexed(Name = "MiningNodePoolSlots_Primary_IDX", Order = 3, Unique = true)]
    public int Position { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
}
