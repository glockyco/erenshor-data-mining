#nullable enable

using SQLite;

[Table("NativeItemBindings")]
public sealed class NativeItemBindingRecord
{
    [PrimaryKey]
    public string BindingKey { get; set; } = string.Empty;

    public string SourceComponentKey { get; set; } = string.Empty;

    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemStableKey { get; set; }
}
