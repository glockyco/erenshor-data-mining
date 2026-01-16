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
    /// Calculated from item frequency in the weighted drop list.
    /// </summary>
    public double DropProbability { get; set; }

    /// <summary>
    /// Whether one item from the pool always drops when the source is used.
    /// True for fossils (one random item always drops).
    /// </summary>
    public bool IsGuaranteed { get; set; }
}
