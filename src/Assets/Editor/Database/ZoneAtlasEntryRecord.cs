#nullable enable

using SQLite;

[Table("ZoneAtlasEntries")]
public class ZoneAtlasEntryRecord
{
    public const string TableName = "ZoneAtlasEntries";

    public int AtlasIndex { get; set; } // Index from the loaded Resources array

    [PrimaryKey]
    public string Id { get; set; } = string.Empty; // From BaseScriptableObject.Id

    public string ZoneName { get; set; } = string.Empty;
    public int LevelRangeLow { get; set; }
    public int LevelRangeHigh { get; set; }
    public bool Dungeon { get; set; }

    public string ResourceName { get; set; } = string.Empty;
}
