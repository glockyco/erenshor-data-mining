#nullable enable

using SQLite;

[Table("CharacterDialogs")]
public class CharacterDialogRecord
{
    public const string TableName = "CharacterDialogs";
    
    [Indexed(Name = "CharacterDialogs_Primary_IDX", Order = 1, Unique = true)]
    public int CharacterId { get; set; } // Id from the Characters table

    [Indexed(Name = "CharacterDialogs_Primary_IDX", Order = 2, Unique = true)]
    public int DialogIndex { get; set; } // Running index for dialogs associated with this character

    public string DialogText { get; set; } = string.Empty; // NPCDialog.Dialog
    public string? Keywords { get; set; } // NPCDialog.KeywordToActivate (serialized as comma-separated string)
    public string? GiveItemName { get; set; } // NPCDialog.GiveItem?.ItemName
    public string? AssignQuestDBName { get; set; } // NPCDialog.QuestToAssign?.DBName
    public string? CompleteQuestDBName { get; set; } // NPCDialog.QuestToComplete?.DBName
    public string? RepeatingQuestDialog { get; set; } // NPCDialog.RepeatingQuestDialog
    public bool KillSelfOnSay { get; set; } // NPCDialog.KillMeOnSay
    public string? RequiredQuestDBName { get; set; } // NPCDialog.RequireQuestComplete?.DBName
    public string? SpawnName { get; set; } // NPCDialog.Spawn?.name
}
