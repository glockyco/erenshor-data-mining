#nullable enable

using SQLite;

[Table("CharacterVendorItems")]
public class CharacterVendorItemRecord
{
    public const string TableName = "CharacterVendorItems";

    [Indexed(Name = "CharacterVendorItems_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterVendorItems_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string ItemStableKey { get; set; } = string.Empty;
}
