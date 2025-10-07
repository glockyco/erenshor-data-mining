#nullable enable

using SQLite;

/// <summary>
/// Represents a crafting recipe reward.
/// Normalizes Item.TemplateRewards (List&lt;Item&gt;) into a proper relational structure
/// with explicit quantities and slot positions.
/// </summary>
[Table("CraftingRewards")]
public class CraftingRewardRecord
{
    public const string TableName = "CraftingRewards";

    /// <summary>
    /// The ID of the recipe item that grants these rewards
    /// </summary>
    [Indexed(Name = "CraftingRewards_Primary_IDX", Order = 1, Unique = true)]
    public string RecipeItemId { get; set; } = string.Empty;

    /// <summary>
    /// The slot position of this reward (1-based).
    /// Preserves the order from Item.TemplateRewards list.
    /// </summary>
    [Indexed(Name = "CraftingRewards_Primary_IDX", Order = 2, Unique = true)]
    public int RewardSlot { get; set; }

    /// <summary>
    /// The ID of the reward item granted
    /// </summary>
    public string RewardItemId { get; set; } = string.Empty;

    /// <summary>
    /// The quantity of this reward item granted.
    /// Extracted by counting duplicates in Item.TemplateRewards list.
    /// </summary>
    public int RewardQuantity { get; set; }
}
