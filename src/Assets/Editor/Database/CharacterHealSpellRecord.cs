#nullable enable

using SQLite;

[Table("CharacterHealSpells")]
public class CharacterHealSpellRecord
{
    public const string TableName = "CharacterHealSpells";

    [Indexed(Name = "CharacterHealSpells_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterHealSpells_Primary_IDX", Order = 2, Unique = true)]
    public string SpellResourceName { get; set; } = string.Empty;
}
