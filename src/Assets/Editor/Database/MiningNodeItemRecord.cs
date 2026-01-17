#nullable enable

using SQLite;

[Table("MiningNodeItems")]
public class MiningNodeItemRecord
{
    public const string TableName = "MiningNodeItems";

    [Indexed(Name = "MiningNodeItems_Primary_IDX", Order = 1, Unique = true)]
    public int MiningNodeId { get; set; }

    [Indexed(Name = "MiningNodeItems_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string ItemStableKey { get; set; } = string.Empty;
    public float DropChance { get; set; }
}
