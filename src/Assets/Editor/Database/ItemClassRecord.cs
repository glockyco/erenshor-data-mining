#nullable enable

using SQLite;

[Table("ItemClasses")]
public class ItemClassRecord
{
    public const string TableName = "ItemClasses";

    [Indexed(Name = "ItemClasses_Primary_IDX", Order = 1, Unique = true)]
    public string ItemId { get; set; } = string.Empty;

    [Indexed(Name = "ItemClasses_Primary_IDX", Order = 2, Unique = true)]
    public string ClassName { get; set; } = string.Empty;
}
