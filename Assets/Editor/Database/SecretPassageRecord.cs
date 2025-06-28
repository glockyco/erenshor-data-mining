#nullable enable

using SQLite;

[Table("SecretPassages")]
public class SecretPassageRecord
{
    public const string TableName = "SecretPassages";
    
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    public string ObjectName { get; set; } = string.Empty;
}