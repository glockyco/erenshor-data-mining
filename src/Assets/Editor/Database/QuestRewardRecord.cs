#nullable enable

using SQLite;

[Table("QuestRewards")]
public class QuestRewardRecord
{
    public const string TableName = "QuestRewards";

    [Indexed(Name = "QuestRewards_Primary_IDX", Order = 1, Unique = true)]
    public int QuestId { get; set; }

    [Indexed(Name = "QuestRewards_Primary_IDX", Order = 2, Unique = true)]
    public string RewardType { get; set; } = string.Empty;  // "XP", "Gold", "Item"

    [Indexed(Name = "QuestRewards_Primary_IDX", Order = 3, Unique = true)]
    public string RewardValue { get; set; } = string.Empty;

    public int Quantity { get; set; } = 1;
}
