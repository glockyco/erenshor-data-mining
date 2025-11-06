#nullable enable

using SQLite;

[Table("ZoneAtlasNeighbors")]
public class ZoneAtlasNeighborRecord
{
    public const string TableName = "ZoneAtlasNeighbors";

    [Indexed(Name = "ZoneAtlasNeighbors_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(ZoneAtlasEntryRecord), "Id")]
    public string ZoneAtlasId { get; set; } = string.Empty;

    [Indexed(Name = "ZoneAtlasNeighbors_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(ZoneRecord), "StableKey")]
    public string NeighborZoneStableKey { get; set; } = string.Empty;
}
