#nullable enable

using SQLite;

[Table("NPCDialogs")]
public class NPCDialogDBRecord
{
    [Indexed(Name = "NPCDialogs_Primary_IDX", Order = 1, Unique = true)]
    public string NPCName { get; set; } // Name from the NPC component on the GameObject

    [Indexed(Name = "NPCDialogs_Primary_IDX", Order = 2, Unique = true)]
    public int DialogIndex { get; set; } // Running index for dialogs associated with this NPC

    public string DialogText { get; set; } = string.Empty; // NPCDialog.Dialog
    public string Keywords { get; set; } = string.Empty; // NPCDialog.KeywordToActivate (serialized as comma-separated string)
    public string GiveItemName { get; set; } = string.Empty; // NPCDialog.GiveItem?.ItemName
    public string AssignQuestDBName { get; set; } = string.Empty; // NPCDialog.QuestToAssign?.DBName
    public string CompleteQuestDBName { get; set; } = string.Empty; // NPCDialog.QuestToComplete?.DBName
    public string RepeatingQuestDialog { get; set; } = string.Empty; // NPCDialog.RepeatingQuestDialog
    public bool KillSelfOnSay { get; set; } // NPCDialog.KillMeOnSay
    public string RequiredQuestDBName { get; set; } = string.Empty; // NPCDialog.RequireQuestComplete?.DBName
    public string SpawnName { get; set; } = string.Empty; // NPCDialog.Spawn?.name
}
