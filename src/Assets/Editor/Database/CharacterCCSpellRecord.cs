#nullable enable

using SQLite;

[Table("CharacterCCSpells")]
public class CharacterCCSpellRecord
{
    public const string TableName = "CharacterCCSpells";

    [Indexed(Name = "CharacterCCSpells_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterCCSpells_Primary_IDX", Order = 2, Unique = true)]
    public string SpellResourceName { get; set; } = string.Empty;
}
