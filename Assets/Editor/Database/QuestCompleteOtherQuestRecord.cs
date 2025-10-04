#nullable enable

using SQLite;

/// <summary>
/// Junction table mapping quests to other quests they complete.
/// Represents the Quest.CompleteOtherQuests relationship.
/// </summary>
[Table("QuestCompleteOtherQuests")]
public class QuestCompleteOtherQuestRecord
{
    public const string TableName = "QuestCompleteOtherQuests";

    /// <summary>
    /// The ID of the quest that triggers completion (Quest.QuestDBIndex).
    /// </summary>
    [Indexed(Name = "QuestCompleteOtherQuests_Primary_IDX", Order = 1, Unique = true)]
    public int QuestId { get; set; }

    /// <summary>
    /// The DBName of the quest that gets completed (Quest.DBName).
    /// </summary>
    [Indexed(Name = "QuestCompleteOtherQuests_Primary_IDX", Order = 2, Unique = true)]
    public string CompletedQuestDBName { get; set; } = string.Empty;
}
