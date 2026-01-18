#nullable enable

using SQLite;

[Table("SpawnPointStopQuests")]
public class SpawnPointStopQuestRecord
{
    public const string TableName = "SpawnPointStopQuests";

    [Indexed(Name = "SpawnPointStopQuests_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(SpawnPointRecord), "StableKey")]
    public string SpawnPointStableKey { get; set; } = string.Empty;

    [Indexed(Name = "SpawnPointStopQuests_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string QuestStableKey { get; set; } = string.Empty;
}
