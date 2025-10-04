#nullable enable

using SQLite;

[Table("CharacterGroupHealSpells")]
public class CharacterGroupHealSpellRecord
{
    public const string TableName = "CharacterGroupHealSpells";

    [Indexed(Name = "CharacterGroupHealSpells_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterGroupHealSpells_Primary_IDX", Order = 2, Unique = true)]
    public int SpellId { get; set; }
}
