#nullable enable

using SQLite;

[Table("SpawnPointStopQuests")]
public class SpawnPointStopQuestRecord
{
    public const string TableName = "SpawnPointStopQuests";

    [Indexed(Name = "SpawnPointStopQuests_Primary_IDX", Order = 1, Unique = true)]
    public int SpawnPointId { get; set; }

    [Indexed(Name = "SpawnPointStopQuests_Primary_IDX", Order = 2, Unique = true)]
    public string QuestDBName { get; set; } = string.Empty;
}
