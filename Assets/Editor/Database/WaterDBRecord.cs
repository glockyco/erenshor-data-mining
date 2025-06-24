#nullable enable

using SQLite;

[Table("Waters")]
public class WaterDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public float Width { get; set; }
    public float Height { get; set; }
    public float Depth { get; set; }
}