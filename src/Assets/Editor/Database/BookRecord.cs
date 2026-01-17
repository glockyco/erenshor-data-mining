#nullable enable

using SQLite;

[Table("Books")]
public class BookRecord
{
    public const string TableName = "Books";

    [Indexed(Name = "Books_Primary_IDX", Order = 1, Unique = true)]
    public string BookTitle { get; set; } = string.Empty;
    [Indexed(Name = "Books_Primary_IDX", Order = 2, Unique = true)]
    public int PageNumber { get; set; }
    public string PageContent { get; set; } = string.Empty;
}
