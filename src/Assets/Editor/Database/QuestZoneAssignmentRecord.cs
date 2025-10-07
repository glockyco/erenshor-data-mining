#nullable enable

using SQLite;

/// <summary>
/// Junction table mapping quests to zones where they are assigned.
/// Represents the ZoneAnnounce.AssignQuestOnEnter relationship.
/// </summary>
[Table("QuestZoneAssignments")]
public class QuestZoneAssignmentRecord
{
    public const string TableName = "QuestZoneAssignments";

    /// <summary>
    /// The DBName of the quest being assigned (Quest.DBName).
    /// </summary>
    [Indexed(Name = "QuestZoneAssignments_Primary_IDX", Order = 1, Unique = true)]
    public string QuestDBName { get; set; } = string.Empty;

    /// <summary>
    /// The scene name of the zone that assigns the quest (ZoneAnnounce.SceneName).
    /// </summary>
    [Indexed(Name = "QuestZoneAssignments_Primary_IDX", Order = 2, Unique = true)]
    public string ZoneSceneName { get; set; } = string.Empty;
}
