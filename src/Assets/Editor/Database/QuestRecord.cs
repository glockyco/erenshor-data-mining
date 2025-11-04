#nullable enable

using SQLite;

[Table("Quests")]
public class QuestRecord
{
    public const string TableName = "Quests";
    
    // --- Core Identification ---
    [PrimaryKey]
    public int QuestDBIndex { get; set; } // Index in the Resources.LoadAll array
    public string QuestName { get; set; } = string.Empty; // From Quest.QuestName (Display Name)
    public string QuestDesc { get; set; } = string.Empty; // From Quest.QuestDesc (Description Text)

    // --- Requirements ---
    // Required items are stored in QuestRequiredItemRecord junction table

    // --- Rewards & Completion ---
    public int XPonComplete { get; set; } // From Quest.XPonComplete
    public string ItemOnCompleteId { get; set; } = string.Empty; // Item ResourceName
    public int GoldOnComplete { get; set; } // From Quest.GoldOnComplete
    public string AssignNewQuestOnCompleteDBName { get; set; } = string.Empty; // "QuestName (DBName)" from Quest.AssignNewQuestOnComplete
    public string CompleteOtherQuestDBNames { get; set; } = string.Empty; // Comma-separated "QuestName (DBName)" from Quest.CompleteOtherQuests

    // --- Dialog & Text ---
    public string DialogOnSuccess { get; set; } = string.Empty; // From Quest.DialogOnSuccess
    public string DialogOnPartialSuccess { get; set; } = string.Empty; // From Quest.DialogOnPartialSuccess
    public string DisableText { get; set; } = string.Empty; // From Quest.DisableText

    // --- Faction Adjustments ---
    public string AffectedFactions { get; set; } = string.Empty; // Comma-separated REFNAMEs from Quest.AffectFactions
    public string AffectedFactionAmounts { get; set; } = string.Empty; // Comma-separated amounts from Quest.AffectFactionAmts

    // --- Flags & Behavior ---
    public bool AssignThisQuestOnPartialComplete { get; set; } // From Quest.AssignThisQuestOnPartialComplete
    public bool Repeatable { get; set; } // From Quest.repeatable
    public bool DisableQuest { get; set; } // From Quest.DisableQuest
    public bool KillTurnInHolder { get; set; } // From Quest.KillTurnInHolder
    public bool DestroyTurnInHolder { get; set; } // From Quest.DestroyTurnInHolder
    public bool DropInvulnOnHolder { get; set; } // From Quest.DropInvulnOnHolder
    public bool OncePerSpawnInstance { get; set; } // From Quest.OncePerSpawnInstance

    // --- Achievements ---
    public string SetAchievementOnGet { get; set; } = string.Empty; // From Quest.SetAchievementOnGet
    public string SetAchievementOnFinish { get; set; } = string.Empty; // From Quest.SetAchievementOnFinish

    // --- Internals / Metadata ---
    public string DBName { get; set; } = string.Empty; // From Quest.DBName (Unique Identifier)
    public string ResourceName { get; set; } = string.Empty; // From Quest.name (ScriptableObject asset name)
}
