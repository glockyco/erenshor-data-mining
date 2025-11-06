#nullable enable

using SQLite;

[Table("CharacterAttackSpells")]
public class CharacterAttackSpellRecord
{
    public const string TableName = "CharacterAttackSpells";

    [Indexed(Name = "CharacterAttackSpells_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty; // FK to Characters.StableKey

    [Indexed(Name = "CharacterAttackSpells_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(SpellRecord), "StableKey")]
    public string SpellStableKey { get; set; } = string.Empty; // FK to Spells.StableKey
}
