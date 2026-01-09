#nullable enable

using SQLite;

/// <summary>
/// Unified junction table for all quest-character relationships.
/// Roles: "giver" (assigns quest), "completer" (dialog completion), "item_turnin" (trade window).
/// </summary>
[Table("QuestCharacterRoles")]
public class QuestCharacterRoleRecord
{
    public const string TableName = "QuestCharacterRoles";

    [Indexed(Name = "QuestCharacterRoles_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string QuestStableKey { get; set; } = string.Empty;

    [Indexed(Name = "QuestCharacterRoles_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "QuestCharacterRoles_Primary_IDX", Order = 3, Unique = true)]
    public string Role { get; set; } = string.Empty;
}
