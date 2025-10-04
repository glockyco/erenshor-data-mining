#nullable enable

using SQLite;

[Table("CharacterAttackSpells")]
public class CharacterAttackSpellRecord
{
    public const string TableName = "CharacterAttackSpells";

    [Indexed(Name = "CharacterAttackSpells_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterAttackSpells_Primary_IDX", Order = 2, Unique = true)]
    public int SpellId { get; set; }
}
