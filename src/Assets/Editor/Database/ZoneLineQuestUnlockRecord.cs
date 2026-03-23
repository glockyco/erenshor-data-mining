#nullable enable

using SQLite;

/// <summary>
/// Records which quests must be completed to unlock a zone line.
/// Multiple rows with the same unlock_group form an AND condition (all required).
/// Multiple groups for the same zone line form an OR condition (any group suffices).
/// </summary>
[Table("ZoneLineQuestUnlocks")]
public class ZoneLineQuestUnlockRecord
{
    public const string TableName = "ZoneLineQuestUnlocks";

    [Indexed(Name = "ZoneLineQuestUnlocks_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(ZoneLineRecord), "StableKey")]
    public string ZoneLineStableKey { get; set; } = string.Empty;

    [Indexed(Name = "ZoneLineQuestUnlocks_Primary_IDX", Order = 2, Unique = true)]
    public int UnlockGroup { get; set; }

    [Indexed(Name = "ZoneLineQuestUnlocks_Primary_IDX", Order = 3, Unique = true)]
    public string QuestDBName { get; set; } = string.Empty;
}
