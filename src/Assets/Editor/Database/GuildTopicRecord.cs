#nullable enable

using SQLite;

[Table("GuildTopics")]
public class GuildTopicRecord
{
    public const string TableName = "GuildTopics";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;
    public int GuildTopicDBIndex { get; set; }
    public string Id { get; set; } = string.Empty;

    // Activation words stored as JSON array
    public string ActivationWords { get; set; } = string.Empty;

    // Responses stored as JSON array
    public string Responses { get; set; } = string.Empty;

    // Relevant scenes stored as JSON array
    public string RelevantScenes { get; set; } = string.Empty;

    public int RequiredLevelToKnow { get; set; }

    public string ResourceName { get; set; } = string.Empty;
}
