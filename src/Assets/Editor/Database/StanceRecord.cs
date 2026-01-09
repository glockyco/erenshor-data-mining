#nullable enable

using SQLite;

[Table("Stances")]
public class StanceRecord
{
    public const string TableName = "Stances";

    [PrimaryKey]
    public string StableKey { get; set; } = string.Empty;
    public int StanceDBIndex { get; set; }
    public string Id { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;

    // Stat Modifiers
    public float MaxHPMod { get; set; }
    public float DamageMod { get; set; }
    public float ProcRateMod { get; set; }
    public float DamageTakenMod { get; set; }
    public float SelfDamagePerAttack { get; set; }
    public float AggroGenMod { get; set; }
    public float SpellDamageMod { get; set; }
    public float SelfDamagePerCast { get; set; }
    public float LifestealAmount { get; set; }
    public float ResonanceAmount { get; set; }
    public bool StopRegen { get; set; }

    // Text
    public string SwitchMessage { get; set; } = string.Empty;
    public string StanceDesc { get; set; } = string.Empty;

    public string ResourceName { get; set; } = string.Empty;
}
