#nullable enable

using SQLite;

[Table("ArenaRounds")]
public class ArenaRoundRecord
{
    public const string TableName = "ArenaRounds";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;

    public string Scene { get; set; } = string.Empty;

    public string ArenaObjectName { get; set; } = string.Empty;

    public int RoundIndex { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string CoinItemStableKey { get; set; } = string.Empty;

    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string AwardChestCharacterStableKey { get; set; } = string.Empty;
    public string? TriggerMode { get; set; }
    public string? EventDisplayName { get; set; }
    public float? EventX { get; set; }
    public float? EventY { get; set; }
    public float? EventZ { get; set; }
    public float? TriggerBoundsCenterX { get; set; }
    public float? TriggerBoundsCenterY { get; set; }
    public float? TriggerBoundsCenterZ { get; set; }
    public float? TriggerBoundsExtentsX { get; set; }
    public float? TriggerBoundsExtentsY { get; set; }
    public float? TriggerBoundsExtentsZ { get; set; }
}
