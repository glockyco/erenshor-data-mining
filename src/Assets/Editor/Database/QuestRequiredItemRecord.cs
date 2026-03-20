#nullable enable

using SQLite;

[Table("QuestRequiredItems")]
public class QuestRequiredItemRecord
{
    public const string TableName = "QuestRequiredItems";

    [Indexed(Name = "QuestRequiredItems_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(QuestVariantRecord), "ResourceName")]
    public string QuestVariantResourceName { get; set; } = string.Empty;

    [Indexed(Name = "QuestRequiredItems_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string ItemStableKey { get; set; } = string.Empty;

    public int Quantity { get; set; }
}
