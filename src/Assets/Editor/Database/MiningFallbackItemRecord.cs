#nullable enable

using SQLite;

[Table("MiningFallbackItems")]
public class MiningFallbackItemRecord
{
    public const string TableName = "MiningFallbackItems";
    public const string GuaranteeSourceKey = "GameManager.GuaranteeMine";

    [PrimaryKey]
    public string SourceKey { get; set; } = string.Empty;

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
}
