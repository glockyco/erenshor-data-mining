#nullable enable

using SQLite;

[Table("CharacterBuffSpells")]
public class CharacterBuffSpellRecord
{
    public const string TableName = "CharacterBuffSpells";

    [Indexed(Name = "CharacterBuffSpells_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterBuffSpells_Primary_IDX", Order = 2, Unique = true)]
    public string SpellResourceName { get; set; } = string.Empty;
}
