#nullable enable

using SQLite;

/// <summary>
/// Junction table mapping quest variants to other quests they complete.
/// Represents the Quest.CompleteOtherQuests relationship.
/// </summary>
[Table("QuestCompleteOtherQuests")]
public class QuestCompleteOtherQuestRecord
{
    public const string TableName = "QuestCompleteOtherQuests";

    [Indexed(Name = "QuestCompleteOtherQuests_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(QuestVariantRecord), "ResourceName")]
    public string QuestVariantResourceName { get; set; } = string.Empty;

    [Indexed(Name = "QuestCompleteOtherQuests_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string CompletedQuestStableKey { get; set; } = string.Empty;
}
