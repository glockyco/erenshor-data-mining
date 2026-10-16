#nullable enable

using SQLite;

// Preserve list positions, including empty entries that a common swap can select.
[Table("CommonWorldItems")]
public class CommonWorldItemRecord
{
    [PrimaryKey]
    public int Position { get; set; }

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
}
