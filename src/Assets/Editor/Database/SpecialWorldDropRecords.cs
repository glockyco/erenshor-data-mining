#nullable enable

using SQLite;

/// <summary>
/// One entry of an item pool that LootTable.InitLootTable rolls as a special
/// world drop on every kill, read from the GameManager and Misc components.
/// </summary>
[Table("SpecialWorldDropItems")]
public class SpecialWorldDropItemRecord
{
    /// <summary>The serialized field name, for example "WorldDropMolds" or "Sivak".</summary>
    [Indexed(Name = "SpecialWorldDropItems_Primary_IDX", Order = 1, Unique = true)]
    public string Pool { get; set; } = string.Empty;

    /// <summary>The list index. Single-item fields use 0.</summary>
    [Indexed(Name = "SpecialWorldDropItems_Primary_IDX", Order = 2, Unique = true)]
    public int Position { get; set; }

    /// <summary>
    /// The item, or null for an empty entry. The game can pick an empty list
    /// entry, so it still counts toward the pool size.
    /// </summary>
    public string? ItemStableKey { get; set; }
}

/// <summary>A boolean GameManager flag that enables or disables a special world drop roll.</summary>
[Table("SpecialWorldDropFlags")]
public class SpecialWorldDropFlagRecord
{
    [PrimaryKey]
    public string Name { get; set; } = string.Empty;

    public bool Value { get; set; }
}
