#nullable enable

using SQLite;

/// <summary>
/// The settings of a character's LootTable that apply to the whole table
/// rather than to one item.
/// </summary>
[Table("CharacterLootTables")]
public class CharacterLootTableRecord
{
    [PrimaryKey]
    public string CharacterStableKey { get; set; } = string.Empty;

    /// <summary>
    /// How many times LootTable.InitLootTable picks an item from
    /// GuaranteeOneDrop. Each roll tries up to ten times for an item that has
    /// not dropped yet.
    /// </summary>
    public int NumberOfGuaranteedDrops { get; set; }
}
