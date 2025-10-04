#nullable enable

using SQLite;

[Table("ItemTemplateIngredients")]
public class ItemTemplateIngredientRecord
{
    public const string TableName = "ItemTemplateIngredients";

    [Indexed(Name = "ItemTemplateIngredients_Primary_IDX", Order = 1, Unique = true)]
    public string ItemId { get; set; } = string.Empty;

    [Indexed(Name = "ItemTemplateIngredients_Primary_IDX", Order = 2, Unique = true)]
    public string IngredientItemId { get; set; } = string.Empty;
}
