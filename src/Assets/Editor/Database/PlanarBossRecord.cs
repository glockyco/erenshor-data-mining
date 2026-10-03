#nullable enable

using SQLite;

/// <summary>
/// A character that a raid plane's <c>PlanarMusicManager</c> names as its big boss or a
/// mid-boss: the game starts the boss music when a character of these spawn points engages.
/// </summary>
[Table("PlanarBosses")]
public class PlanarBossRecord
{
    public const string TableName = "PlanarBosses";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;

    /// <summary><c>boss</c> for <c>BigBossSpawn</c>, <c>midboss</c> for <c>MidBossSpawns</c>.</summary>
    public string Role { get; set; } = string.Empty;

    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;
}
