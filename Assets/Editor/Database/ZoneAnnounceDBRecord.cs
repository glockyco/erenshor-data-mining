using SQLite;

[Table("ZoneAnnounces")]
public class ZoneAnnounceDBRecord
{
    [PrimaryKey]
    public string SceneName { get; set; }
    public string ZoneName { get; set; }
    public bool IsDungeon { get; set; }

    public string Achievement { get; set; }
    public string CompleteQuestOnEnter { get; set; }
    public string CompleteSecondQuestOnEnter { get; set; }
    public string AssignQuestOnEnter { get; set; }
}
