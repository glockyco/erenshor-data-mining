using SQLite;

[Table("AchievementTriggers")]
public class AchievementTriggerDBRecord
{
    [PrimaryKey]
    public string Id { get; set; } // SceneName + Position

    public string SceneName { get; set; }
    public float PositionX { get; set; }
    public float PositionY { get; set; }
    public float PositionZ { get; set; }
    
    public string AchievementName { get; set; }
}