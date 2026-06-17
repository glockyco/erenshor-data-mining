#nullable enable

using SQLite;

[Table("ArenaRoundEnemies")]
public class ArenaRoundEnemyRecord
{
    public const string TableName = "ArenaRoundEnemies";

    [Indexed(Name = "ArenaRoundEnemies_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(ArenaRoundRecord), "StableKey")]
    public string ArenaRoundStableKey { get; set; } = string.Empty;

    [Indexed(Name = "ArenaRoundEnemies_Primary_IDX", Order = 2, Unique = true)]
    public int SequenceIndex { get; set; }

    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string EnemyCharacterStableKey { get; set; } = string.Empty;
}
