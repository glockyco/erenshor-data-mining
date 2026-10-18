#nullable enable

using SQLite;

/// <summary>
/// Junction table for all quest completion sources.
/// Single source of truth for "how do I complete this quest?"
///
/// Methods:
/// - item_turnin: Trade items to NPC via QuestManager
/// - talk: Dialog completion via NPCDialog.QuestToComplete
/// - zone: Zone entry via ZoneAnnounce.CompleteQuestOnEnter
/// - read: Item read via Item.CompleteOnRead
/// - shout: NPC shout via NPCShoutListener.TriggerQuest
/// - chain: Only completed via QuestCompleteOtherQuests (no independent method)
/// </summary>
[Table("QuestCompletionSources")]
public class QuestCompletionSourceRecord
{
    public const string TableName = "QuestCompletionSources";

    [Indexed(Name = "QuestCompletionSources_Quest_IDX")]
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string QuestStableKey { get; set; } = string.Empty;

    /// <summary>
    /// Completion method: item_turnin, talk, zone, read, shout, death, chain
    /// </summary>
    public string Method { get; set; } = string.Empty;

    /// <summary>
    /// Source entity type: character, zone, item, quest
    /// </summary>
    public string SourceType { get; set; } = string.Empty;

    /// <summary>
    /// Reference to the source entity
    /// </summary>
    public string? SourceStableKey { get; set; }

    /// <summary>
    /// Human-readable note
    /// </summary>
    public string? Note { get; set; }
}
