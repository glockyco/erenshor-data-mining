using SQLite;

[Table("Waters")]
public class WaterDBRecord
{
    [PrimaryKey]
    public string Id { get; set; } // SceneName(WaterIndex)
    public string SceneName { get; set; }
    public int Index { get; set; }
}