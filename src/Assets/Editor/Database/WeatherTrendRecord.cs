#nullable enable

using SQLite;

[Table("WeatherTrends")]
public sealed class WeatherTrendRecord
{
    [PrimaryKey]
    public string StableKey { get; set; } = "";
    public string Scene { get; set; } = "";
    public bool IsEnabled { get; set; }
    public float MaxNaturalCloudy { get; set; }
    public float MaxNaturalRainy { get; set; }
}
