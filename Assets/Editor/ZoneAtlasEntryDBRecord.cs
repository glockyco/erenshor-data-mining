using SQLite;

[Table("ZoneAtlasEntries")]
public class ZoneAtlasEntryDBRecord
{
    public int AtlasIndex { get; set; } // Index from the loaded Resources array

    [PrimaryKey]
    public string Id { get; set; } // From BaseScriptableObject.Id

    public string ZoneName { get; set; }
    public int LevelRangeLow { get; set; }
    public int LevelRangeHigh { get; set; }
    public bool Dungeon { get; set; }

    // Store the list as a comma-separated string
    public string NeighboringZones { get; set; }

    // Note: curPop is a runtime value and typically not exported as static data.

    public string ResourceName { get; set; } // The filename of the ScriptableObject asset
}
