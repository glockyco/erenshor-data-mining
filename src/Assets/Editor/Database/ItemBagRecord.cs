#nullable enable

using SQLite;

[Table("ItemBags")]
public class ItemBagRecord
{
    public const string TableName = "ItemBags";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }

    [Indexed]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
    public bool Respawns { get; set; }
    public float RespawnTimer { get; set; }
}
