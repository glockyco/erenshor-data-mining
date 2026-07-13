#nullable enable

using SQLite;

[Table("DynamicCharacterSpawns")]
public class DynamicCharacterSpawnRecord
{
    public const string TableName = "DynamicCharacterSpawns";

    [PrimaryKey]
    public string Key { get; set; } = string.Empty;
    public string CharacterStableKey { get; set; } = string.Empty;
    public string Scene { get; set; } = string.Empty;
    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
    public string SourceScript { get; set; } = string.Empty;
    public float? EventX { get; set; }
    public float? EventY { get; set; }
    public float? EventZ { get; set; }
    public string? TriggerItemStableKey { get; set; }
    public string? TriggerMode { get; set; }
    public string? EventDisplayName { get; set; }
    public float? TriggerBoundsCenterX { get; set; }
    public float? TriggerBoundsCenterY { get; set; }
    public float? TriggerBoundsCenterZ { get; set; }
    public float? TriggerBoundsExtentsX { get; set; }
    public float? TriggerBoundsExtentsY { get; set; }
    public float? TriggerBoundsExtentsZ { get; set; }
}
