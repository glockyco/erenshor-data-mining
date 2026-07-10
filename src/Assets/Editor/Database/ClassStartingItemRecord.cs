#nullable enable

using SQLite;

[Table("ClassStartingItems")]
public class ClassStartingItemRecord
{
    public const string TableName = "ClassStartingItems";

    [Indexed(Name = "ClassStartingItems_Primary_IDX", Order = 1, Unique = true)]
    public string ClassName { get; set; } = string.Empty;

    [Indexed(Name = "ClassStartingItems_Primary_IDX", Order = 2, Unique = true)]
    public int SortOrder { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string ItemStableKey { get; set; } = string.Empty;
}
