#nullable enable

using SQLite;

[Table("WikiComparison")]
public class WikiComparisonRecord
{
    public const string TableName = "WikiComparison";
    
    public string WikiUrl { get; set; } = string.Empty;
    public string Type { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public int Tier { get; set; }
    public string ComparisonResult { get; set; } = string.Empty;
    public string CurrentWikiString { get; set; } = string.Empty;
    public string SuggestedWikiString { get; set; } = string.Empty;
    public string ComparisonTimestamp { get; set; } = string.Empty;
}