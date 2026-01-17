#nullable enable

using SQLite;

[Table("CharacterDialogs")]
public class CharacterDialogRecord
{
    public const string TableName = "CharacterDialogs";

    [Indexed(Name = "CharacterDialogs_Primary_IDX", Order = 1, Unique = true)]
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string CharacterStableKey { get; set; } = string.Empty;

    [Indexed(Name = "CharacterDialogs_Primary_IDX", Order = 2, Unique = true)]
    public int DialogIndex { get; set; } // Running index for dialogs associated with this character

    public string DialogText { get; set; } = string.Empty;
    public string? Keywords { get; set; }
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? GiveItemStableKey { get; set; }
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? AssignQuestStableKey { get; set; }
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? CompleteQuestStableKey { get; set; }
    public string? RepeatingQuestDialog { get; set; }
    public bool KillSelfOnSay { get; set; }
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? RequiredQuestStableKey { get; set; }
    [ForeignKey(typeof(CharacterRecord), "StableKey")]
    public string? SpawnCharacterStableKey { get; set; }
}
