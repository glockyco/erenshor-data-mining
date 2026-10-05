#nullable enable

using SQLite;

/// <summary>
/// One entry of the knowledge base that simulated-player chat reads
/// (KnowledgeDatabaseAsset, shipped as KnowledgeDatabaseHolder.asset).
/// The entry is exported as the game ships it, without corrections.
/// </summary>
[Table("KnowledgeEntries")]
public class KnowledgeEntryRecord
{
    /// <summary>The index in KnowledgeDatabaseAsset.Entries. Chat reads the entries in this order.</summary>
    [PrimaryKey]
    public int Position { get; set; }

    public string NPCName { get; set; } = string.Empty;

    /// <summary>The zone display name, or null when the entry has none.</summary>
    public string? ZoneName { get; set; }

    public int Level { get; set; }

    public bool IsBoss { get; set; }

    /// <summary>
    /// "NPCs/" followed by the file name of the prefab the entry was built
    /// from. The game never loads this path.
    /// </summary>
    public string PrefabPath { get; set; } = string.Empty;
}

/// <summary>One item name in the Drops list of a knowledge entry.</summary>
[Table("KnowledgeEntryDrops")]
public class KnowledgeEntryDropRecord
{
    [Indexed(Name = "KnowledgeEntryDrops_Primary_IDX", Order = 1, Unique = true)]
    public int EntryPosition { get; set; }

    /// <summary>The list index. A name can repeat.</summary>
    [Indexed(Name = "KnowledgeEntryDrops_Primary_IDX", Order = 2, Unique = true)]
    public int Position { get; set; }

    public string ItemName { get; set; } = string.Empty;
}
