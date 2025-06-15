using SQLite;

[Table("MiningNodeItems")]
public class MiningNodeItemDBRecord
{
    [Indexed(Name = "MiningNodeItems_Primary_IDX", Order = 1, Unique = true)]
    public int MiningNodeId { get; set; } // Foreign key to MiningNodes.Id

    [Indexed(Name = "MiningNodeItems_Primary_IDX", Order = 2, Unique = true)]
    public string Rarity { get; set; } // "Common", "Rare", "Legend", "Guarantee"

    [Indexed(Name = "MiningNodeItems_Primary_IDX", Order = 3, Unique = true)]
    public int RarityIndex { get; set; } // Running index for items within this Rarity category for this MiningNodeId

    public string ItemName { get; set; }
    public float DropChance { get; set; } // Probability of this item dropping (0.0 to 100.0)
    public float TotalDropChance { get; set; } // Total probability of this item dropping from the node (0.0 to 100.0)
}
