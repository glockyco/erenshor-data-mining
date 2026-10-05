#nullable enable

using SQLite;

/// <summary>
/// One entry of Item.TemplateRewards (List&lt;Item&gt;), keyed by its list position.
/// </summary>
[Table("CraftingRewards")]
public class CraftingRewardRecord
{
    public const string TableName = "CraftingRewards";

    /// <summary>
    /// The stable key of the recipe item that grants these rewards
    /// </summary>
    [Indexed(Name = "CraftingRewards_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string RecipeItemStableKey { get; set; } = string.Empty;

    /// <summary>
    /// The list position of this entry plus one. Slot 1 is TemplateRewards[0],
    /// the only reward that the forge awards.
    /// </summary>
    [Indexed(Name = "CraftingRewards_Primary_IDX", Order = 2, Unique = true)]
    public int RewardSlot { get; set; }

    /// <summary>
    /// The stable key of the reward item granted
    /// </summary>
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string RewardItemStableKey { get; set; } = string.Empty;

    /// <summary>
    /// The number of items in this entry. Each list entry is one item.
    /// </summary>
    public int RewardQuantity { get; set; }
}
