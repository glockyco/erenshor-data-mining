using SQLite;

[Table("MiningNodeItems")]
public class MiningNodeItemDBRecord
{
    [PrimaryKey]
    public string MiningNodeId { get; set; } // Foreign key to MiningNodes.Id

    [PrimaryKey]
    public string Rarity { get; set; } // "Common", "Rare", "Legend", "Guarantee"

    [PrimaryKey]
    public int RarityIndex { get; set; } // Running index for items within this Rarity category for this MiningNodeId

    public string ItemName { get; set; }
    public float DropChance { get; set; } // Probability of this item dropping (0.0 to 100.0)
    public float TotalDropChance { get; set; } // Total probability of this item dropping from the node (0.0 to 100.0)
}
