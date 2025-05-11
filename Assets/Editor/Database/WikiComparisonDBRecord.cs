using SQLite;

[Table("WikiComparison")]
public class WikiComparisonDBRecord
{
    public string WikiUrl { get; set;}
    public string Type { get; set; }
    public string Name { get; set; }
    public int Tier { get; set; }
    public string ComparisonResult { get; set; }
    public string CurrentWikiString { get; set; }
    public string SuggestedWikiString { get; set; }
    public string ComparisonTimestamp { get; set; }
}