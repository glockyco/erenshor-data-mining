#nullable enable

using SQLite;

/// <summary>
/// The native singleton field used for an item-use pool roll.
/// </summary>
[Table("ItemDropPools")]
public class ItemDropPoolRecord
{
    [PrimaryKey]
    public string PoolStableKey { get; set; } = string.Empty;

    public string SourceComponentKey { get; set; } = string.Empty;

    public int SlotCount { get; set; }
}

/// <summary>
/// Native zero-based positions retain weighting, duplicate references, and null slots.
/// </summary>
[Table("ItemDropPoolSlots")]
public class ItemDropPoolSlotRecord
{
    [Indexed(Name = "ItemDropPoolSlots_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(ItemDropPoolRecord), "PoolStableKey")]
    public string PoolStableKey { get; set; } = string.Empty;

    [Indexed(Name = "ItemDropPoolSlots_Primary_IDX", Order = 2, Unique = true)]
    public int Position { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
}
