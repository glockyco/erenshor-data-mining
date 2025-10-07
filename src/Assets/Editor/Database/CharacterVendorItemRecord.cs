#nullable enable

using SQLite;

[Table("CharacterVendorItems")]
public class CharacterVendorItemRecord
{
    public const string TableName = "CharacterVendorItems";

    [Indexed(Name = "CharacterVendorItems_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; }

    [Indexed(Name = "CharacterVendorItems_Primary_IDX", Order = 2, Unique = true)]
    public string ItemName { get; set; } = string.Empty;
}
