#nullable enable

using SQLite;

[Table("SpawnPointEssentialLinks")]
public class SpawnPointEssentialLinkRecord
{
    public const string TableName = "SpawnPointEssentialLinks";

    [Indexed(Name = "SpawnPointEssentialLinks_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(SpawnPointRecord), "StableKey")]
    public string SourceSpawnPointStableKey { get; set; } = string.Empty;

    [Indexed(Name = "SpawnPointEssentialLinks_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(SpawnPointRecord), "StableKey")]
    public string EssentialSpawnPointStableKey { get; set; } = string.Empty;

    public string? SourceScene { get; set; }
}
