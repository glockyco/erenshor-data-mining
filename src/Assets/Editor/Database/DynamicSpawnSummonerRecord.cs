#nullable enable

using SQLite;

/// <summary>
/// One summoner of a dynamic spawn field, from the field's <c>summoned_by</c> in
/// dynamic-spawn-catalog.toml. A spawn row joins its summoners by controller
/// object and field.
/// </summary>
[Table("DynamicSpawnSummoners")]
public class DynamicSpawnSummonerRecord
{
    public const string TableName = "DynamicSpawnSummoners";

    [Indexed(Name = "DynamicSpawnSummoners_Primary_IDX", Order = 1, Unique = true)]
    public string ControllerObjectKey { get; set; } = string.Empty;

    [Indexed(Name = "DynamicSpawnSummoners_Primary_IDX", Order = 2, Unique = true)]
    public string SourceField { get; set; } = string.Empty;

    [Indexed(Name = "DynamicSpawnSummoners_Primary_IDX", Order = 3, Unique = true)]
    public int SummonerIndex { get; set; }

    public string SourceScript { get; set; } = string.Empty;

    // "alive", "defeated", or "dialog".
    public string Summon { get; set; } = string.Empty;

    // "character", "spawn_point", or "checked_in", whose characters the clean
    // build reads from the controller's check-in.
    public string SummonerKind { get; set; } = string.Empty;
    public string? SummonerStableKey { get; set; }
}
