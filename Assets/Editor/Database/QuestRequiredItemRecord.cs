#nullable enable

using SQLite;

[Table("QuestRequiredItems")]
public class QuestRequiredItemRecord
{
    public const string TableName = "QuestRequiredItems";

    [Indexed(Name = "QuestRequiredItems_Primary_IDX", Order = 1, Unique = true)]
    public int QuestId { get; set; }

    [Indexed(Name = "QuestRequiredItems_Primary_IDX", Order = 2, Unique = true)]
    public string ItemId { get; set; } = string.Empty;
}
