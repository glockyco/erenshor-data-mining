#nullable enable

using SQLite;

[Table("CharacterQuestManagerQuests")]
public class CharacterQuestManagerRecord
{
    public const string TableName = "CharacterQuestManagerQuests";

    [Indexed(Name = "CharacterQuestManagerQuests_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterQuestManagerQuests_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string QuestStableKey { get; set; } = string.Empty;
}
