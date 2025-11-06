#nullable enable

using SQLite;

[Table("SpawnPointCharacters")]
public class SpawnPointCharacterRecord
{
    public const string TableName = "SpawnPointCharacters";

    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 1, Unique = true)]
    public int SpawnPointId { get; set; }
    [Indexed(Name = "SpawnPointCharacters_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;
    public float SpawnChance { get; set; }
    public bool IsCommon { get; set; }
    public bool IsRare { get; set; }
}
