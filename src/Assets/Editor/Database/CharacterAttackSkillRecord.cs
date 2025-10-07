#nullable enable

using SQLite;

[Table("CharacterAttackSkills")]
public class CharacterAttackSkillRecord
{
    public const string TableName = "CharacterAttackSkills";

    [Indexed(Name = "CharacterAttackSkills_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterAttackSkills_Primary_IDX", Order = 2, Unique = true)]
    public int SkillId { get; set; }
}
