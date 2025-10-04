#nullable enable

using SQLite;

[Table("ItemTemplateRewards")]
public class ItemTemplateRewardRecord
{
    public const string TableName = "ItemTemplateRewards";

    [Indexed(Name = "ItemTemplateRewards_Primary_IDX", Order = 1, Unique = true)]
    public string ItemId { get; set; } = string.Empty;

    [Indexed(Name = "ItemTemplateRewards_Primary_IDX", Order = 2, Unique = true)]
    public string RewardItemId { get; set; } = string.Empty;
}
