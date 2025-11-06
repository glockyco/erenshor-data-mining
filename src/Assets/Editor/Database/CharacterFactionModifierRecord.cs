#nullable enable

using SQLite;

[Table("CharacterFactionModifiers")]
public class CharacterFactionModifierRecord
{
    public const string TableName = "CharacterFactionModifiers";

    [Indexed(Name = "CharacterFactionModifiers_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterFactionModifiers_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(WorldFactionRecord), "StableKey")]
    public string FactionStableKey { get; set; } = string.Empty;

    public int ModifierValue { get; set; }
}
