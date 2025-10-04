#nullable enable

using SQLite;

[Table("CharacterFactionModifiers")]
public class CharacterFactionModifierRecord
{
    public const string TableName = "CharacterFactionModifiers";

    [Indexed(Name = "CharacterFactionModifiers_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterFactionModifiers_Primary_IDX", Order = 2, Unique = true)]
    public string FactionREFNAME { get; set; } = string.Empty;

    public int ModifierValue { get; set; }
}
