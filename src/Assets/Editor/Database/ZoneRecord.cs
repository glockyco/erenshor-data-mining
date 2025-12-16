#nullable enable

using SQLite;

[Table("Zones")]
public class ZoneRecord
{
    public const string TableName = "Zones";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty; // Stable identifier: "zone:scene"
    public string SceneName { get; set; } = string.Empty;
    public string ZoneName { get; set; } = string.Empty;
    public bool IsDungeon { get; set; }

    public string Achievement { get; set; } = string.Empty;
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? CompleteQuestOnEnterStableKey { get; set; }
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? CompleteSecondQuestOnEnterStableKey { get; set; }
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? AssignQuestOnEnterStableKey { get; set; }

    // North bearing for compass orientation (in degrees, from ZoneAnnounce Y rotation)
    public float NorthBearing { get; set; }
}
