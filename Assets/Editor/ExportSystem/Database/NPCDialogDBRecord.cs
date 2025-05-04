using SQLite;

[Table("NPCDialogs")]
public class NPCDialogDBRecord
{
    [PrimaryKey, Indexed]
    public string NPCName { get; set; } // Name from the NPC component on the GameObject

    [PrimaryKey]
    public int DialogIndex { get; set; } // Running index for dialogs associated with this NPC

    public string DialogText { get; set; } // NPCDialog.Dialog
    public string Keywords { get; set; } // NPCDialog.KeywordToActivate (serialized as comma-separated string)
    public string GiveItemName { get; set; } // NPCDialog.GiveItem?.ItemName
    public string AssignQuestDBName { get; set; } // NPCDialog.QuestToAssign?.DBName
    public string CompleteQuestDBName { get; set; } // NPCDialog.QuestToComplete?.DBName
    public string RepeatingQuestDialog { get; set; } // NPCDialog.RepeatingQuestDialog
    public bool KillSelfOnSay { get; set; } // NPCDialog.KillMeOnSay
    public string RequiredQuestDBName { get; set; } // NPCDialog.RequireQuestComplete?.DBName
    public string SpawnName { get; set; } // NPCDialog.Spawn?.name
}
