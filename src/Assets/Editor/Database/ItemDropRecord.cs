#nullable enable

using SQLite;

/// <summary>
/// Records items that can drop from using other items (e.g., Braxonian Fossil).
/// Stores drop probabilities calculated from weighted item lists.
/// </summary>
[Table("ItemDrops")]
public class ItemDropRecord
{
    public const string TableName = "ItemDrops";

    [Indexed(Name = "ItemDrops_Primary_IDX", Order = 3, Unique = true)]
    [ForeignKey(typeof(ItemDropPoolRecord), "PoolStableKey")]
    public string PoolStableKey { get; set; } = string.Empty;

    /// <summary>
    /// Stable key of the source item that produces drops when used.
    /// Format: "item:resource_name" (e.g., "item:gen - braxonian fossil")
    /// </summary>
    [Indexed(Name = "ItemDrops_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string SourceItemStableKey { get; set; } = string.Empty;

    /// <summary>
    /// Stable key of the item that can drop.
    /// Format: "item:resource_name" (e.g., "item:gen - time stone")
    /// </summary>
    [Indexed(Name = "ItemDrops_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string DroppedItemStableKey { get; set; } = string.Empty;

    /// <summary>
    /// Probability that this specific item drops (as percentage, 0-100).
    /// Calculated from item frequency divided by all native slots, including nulls.
    /// </summary>
    public double DropProbability { get; set; }

    /// <summary>
    /// Whether using the source performs a guaranteed pool roll, not a guaranteed item grant.
    /// </summary>
    public bool IsGuaranteed { get; set; }
}
