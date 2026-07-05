#nullable enable

using SQLite;

[Table("CharacterAEEvents")]
public class CharacterAEEventRecord
{
    public const string TableName = "CharacterAEEvents";

    [Indexed(Name = "CharacterAEEvents_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterAEEvents_Primary_IDX", Order = 2, Unique = true)]
    public string ComponentType { get; set; } = string.Empty;

    public int TickDamage { get; set; }
    public float? TickTime { get; set; }
    public int? TickRange { get; set; }
    public int? ResistModifier { get; set; }
    public string? ResistType { get; set; }
    public string? EventHappens { get; set; }
    public string? DamageReason { get; set; }
    public string? AddEffectSpellStableKey { get; set; }
    public bool? IsLifetap { get; set; }
    public float? LifetapHealMod { get; set; }
    public bool? TriggerOnly { get; set; }
}
