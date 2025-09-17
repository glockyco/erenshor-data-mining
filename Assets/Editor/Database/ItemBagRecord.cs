#nullable enable

using SQLite;

[Table("ItemBags")]
public class ItemBagRecord
{
    public const string TableName = "ItemBags";

    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    [Indexed]
    public int CoordinateId { get; set; }
    [Indexed]
    public string? ItemId { get; set; }
    public bool Respawns { get; set; }
    public float RespawnTimer { get; set; }
}