#nullable enable

using SQLite;

/// <summary>
/// Records which quests must be completed for a character to spawn.
/// Multiple rows with the same unlock_group form an AND condition (all required).
/// Multiple groups for the same character form an OR condition (any group suffices).
/// </summary>
[Table("CharacterQuestUnlocks")]
public class CharacterQuestUnlockRecord
{
    public const string TableName = "CharacterQuestUnlocks";

    [Indexed(Name = "CharacterQuestUnlocks_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterQuestUnlocks_Primary_IDX", Order = 2, Unique = true)]
    public int UnlockGroup { get; set; }

    [Indexed(Name = "CharacterQuestUnlocks_Primary_IDX", Order = 3, Unique = true)]
    public string QuestDBName { get; set; } = string.Empty;
}
