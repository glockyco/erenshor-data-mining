#nullable enable

using SQLite;

/// <summary>
/// Represents a crafting recipe material requirement.
/// Normalizes Item.TemplateIngredients (List&lt;Item&gt;) into a proper relational structure
/// with explicit quantities and slot positions.
/// </summary>
[Table("CraftingRecipes")]
public class CraftingRecipeRecord
{
    public const string TableName = "CraftingRecipes";

    /// <summary>
    /// The ID of the item that is crafted (the recipe/template item)
    /// </summary>
    [Indexed(Name = "CraftingRecipes_Primary_IDX", Order = 1, Unique = true)]
    public string RecipeItemId { get; set; } = string.Empty;

    /// <summary>
    /// The slot position of this material in the recipe (1-based).
    /// Preserves the order from Item.TemplateIngredients list.
    /// </summary>
    [Indexed(Name = "CraftingRecipes_Primary_IDX", Order = 2, Unique = true)]
    public int MaterialSlot { get; set; }

    /// <summary>
    /// The ID of the material item required for this slot
    /// </summary>
    public string MaterialItemId { get; set; } = string.Empty;

    /// <summary>
    /// The quantity of this material required.
    /// Extracted by counting duplicates in Item.TemplateIngredients list.
    /// </summary>
    public int MaterialQuantity { get; set; }
}
