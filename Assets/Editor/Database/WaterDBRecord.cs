using SQLite;

[Table("Waters")]
public class WaterDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
}