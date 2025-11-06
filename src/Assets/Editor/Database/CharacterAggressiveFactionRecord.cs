#nullable enable

using SQLite;

[Table("CharacterAggressiveFactions")]
public class CharacterAggressiveFactionRecord
{
    public const string TableName = "CharacterAggressiveFactions";

    [Indexed(Name = "CharacterAggressiveFactions_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterAggressiveFactions_Primary_IDX", Order = 2, Unique = true)]
    public string FactionName { get; set; } = string.Empty; // Faction enum value (Player, Enemy, etc), NOT WorldFaction
}
