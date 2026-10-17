#nullable enable

using SQLite;

[Table("ZoneWideSpawnCandidates")]
public class ZoneWideSpawnCandidateRecord
{
    public const string TableName = "ZoneWideSpawnCandidates";

    [PrimaryKey]
    public string Key { get; set; } = string.Empty;
    public string RuleId { get; set; } = string.Empty;
    public int Slot { get; set; }

    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;
}
