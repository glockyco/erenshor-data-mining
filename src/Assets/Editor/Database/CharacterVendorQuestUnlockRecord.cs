#nullable enable

using SQLite;

[Table("CharacterVendorQuestUnlocks")]
public class CharacterVendorQuestUnlockRecord
{
    public const string TableName = "CharacterVendorQuestUnlocks";

    [Indexed(Name = "CharacterVendorQuestUnlocks_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterVendorQuestUnlocks_Primary_IDX", Order = 2, Unique = true)]
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string QuestStableKey { get; set; } = string.Empty;
}
