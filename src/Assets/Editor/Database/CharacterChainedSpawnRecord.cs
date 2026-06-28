#nullable enable

using SQLite;

[Table("CharacterChainedSpawns")]
public class CharacterChainedSpawnRecord
{
    public const string TableName = "CharacterChainedSpawns";

    [Indexed(Name = "CharacterChainedSpawns_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string ParentStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterChainedSpawns_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string ChildStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterChainedSpawns_Primary_IDX", Order = 3, Unique = true)]
    public string SourceScript { get; set; } = string.Empty;
}
