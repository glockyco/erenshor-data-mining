using SQLite;

[Table("MiningNodeItems")]
public class MiningNodeItemDBRecord
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }

    [Indexed]
    public string MiningNodeId { get; set; } // Foreign key to MiningNodes.Id

    public string ItemName { get; set; }
    public string Rarity { get; set; } // "Common", "Rare", "Legend", "Guarantee"
    public float DropChance { get; set; } // Probability of this item dropping (0.0 to 1.0)
    public float TotalDropChance { get; set; } // Total probability of this item dropping from the node
}
