#nullable enable

using SQLite;

[Table("CharacterTauntSpells")]
public class CharacterTauntSpellRecord
{
    public const string TableName = "CharacterTauntSpells";

    [Indexed(Name = "CharacterTauntSpells_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterTauntSpells_Primary_IDX", Order = 2, Unique = true)]
    public string SpellResourceName { get; set; } = string.Empty;
}
