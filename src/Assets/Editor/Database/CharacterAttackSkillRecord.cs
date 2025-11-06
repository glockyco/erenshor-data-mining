#nullable enable

using SQLite;

[Table("CharacterAttackSkills")]
public class CharacterAttackSkillRecord
{
    public const string TableName = "CharacterAttackSkills";

    [Indexed(Name = "CharacterAttackSkills_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterAttackSkills_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(SkillRecord), "StableKey")]
    public string SkillStableKey { get; set; } = string.Empty;
}
