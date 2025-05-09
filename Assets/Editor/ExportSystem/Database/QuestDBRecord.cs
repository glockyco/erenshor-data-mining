using SQLite;

[Table("Quests")]
public class QuestDBRecord
{
    // --- Core Identification ---
    public int QuestDBIndex { get; set; } // Index in the Resources.LoadAll array
    public string QuestName { get; set; } // From Quest.QuestName (Display Name)
    public string QuestDesc { get; set; } // From Quest.QuestDesc (Description Text)

    // --- Requirements ---
    public string RequiredItemIds { get; set; } // Comma-separated IDs from Quest.RequiredItems

    // --- Rewards & Completion ---
    public int XPonComplete { get; set; } // From Quest.XPonComplete
    public string ItemOnCompleteId { get; set; } // ID from Quest.ItemOnComplete
    public int GoldOnComplete { get; set; } // From Quest.GoldOnComplete
    public string AssignNewQuestOnCompleteDBName { get; set; } // DBName from Quest.AssignNewQuestOnComplete
    public string CompleteOtherQuestDBNames { get; set; } // Comma-separated DBNames from Quest.CompleteOtherQuests

    // --- Dialog & Text ---
    public string DialogOnSuccess { get; set; } // From Quest.DialogOnSuccess
    public string DialogOnPartialSuccess { get; set; } // From Quest.DialogOnPartialSuccess
    public string DisableText { get; set; } // From Quest.DisableText

    // --- Faction Adjustments ---
    public string AffectedFactions { get; set; } // Comma-separated REFNAMEs from Quest.AffectFactions
    public string AffectedFactionAmounts { get; set; } // Comma-separated amounts from Quest.AffectFactionAmts

    // --- Flags & Behavior ---
    public bool AssignThisQuestOnPartialComplete { get; set; } // From Quest.AssignThisQuestOnPartialComplete
    public bool Repeatable { get; set; } // From Quest.repeatable
    public bool DisableQuest { get; set; } // From Quest.DisableQuest
    public bool KillTurnInHolder { get; set; } // From Quest.KillTurnInHolder
    public bool DestroyTurnInHolder { get; set; } // From Quest.DestroyTurnInHolder
    public bool DropInvulnOnHolder { get; set; } // From Quest.DropInvulnOnHolder
    public bool OncePerSpawnInstance { get; set; } // From Quest.OncePerSpawnInstance

    // --- Achievements ---
    public string SetAchievementOnGet { get; set; } // From Quest.SetAchievementOnGet
    public string SetAchievementOnFinish { get; set; } // From Quest.SetAchievementOnFinish

    // --- Internals / Metadata ---
    public string DBName { get; set; } // From Quest.DBName (Unique Identifier)
    [PrimaryKey]
    public string ResourceName { get; set; } // From Quest.name (ScriptableObject asset name)
}
