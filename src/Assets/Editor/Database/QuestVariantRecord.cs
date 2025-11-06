#nullable enable

using SQLite;

/// <summary>
/// Quest variant table - stores all Quest ScriptableObjects with their full data.
/// Multiple variants can have the same DBName (different completion paths for same quest).
/// </summary>
[Table("QuestVariants")]
public class QuestVariantRecord
{
    public const string TableName = "QuestVariants";

    // --- Core Identification ---
    [PrimaryKey]
    public string ResourceName { get; set; } = string.Empty; // ScriptableObject filename (unique)
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string QuestStableKey { get; set; } = string.Empty; // FK to Quests table
    public int QuestDBIndex { get; set; } // Index in Resources.LoadAll array
    public string QuestName { get; set; } = string.Empty; // Display name
    public string QuestDesc { get; set; } = string.Empty; // Description text

    // --- Rewards & Completion ---
    public int XPonComplete { get; set; }
    [ForeignKey(typeof(ItemRecord), "StableKey")]
    public string? ItemOnCompleteStableKey { get; set; }
    public int GoldOnComplete { get; set; }
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string? AssignNewQuestOnCompleteStableKey { get; set; }

    // --- Dialog & Text ---
    public string DialogOnSuccess { get; set; } = string.Empty;
    public string DialogOnPartialSuccess { get; set; } = string.Empty;
    public string DisableText { get; set; } = string.Empty;

    // --- Flags & Behavior ---
    public bool AssignThisQuestOnPartialComplete { get; set; }
    public bool Repeatable { get; set; }
    public bool DisableQuest { get; set; }
    public bool KillTurnInHolder { get; set; }
    public bool DestroyTurnInHolder { get; set; }
    public bool DropInvulnOnHolder { get; set; }
    public bool OncePerSpawnInstance { get; set; }

    // --- Achievements ---
    public string SetAchievementOnGet { get; set; } = string.Empty;
    public string SetAchievementOnFinish { get; set; } = string.Empty;
}
