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
/// - scripted: Hardcoded in Unity scripts (AngelScript, SivTorchLight, ShiverEvent)
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
    /// Completion method: item_turnin, talk, zone, read, shout, scripted, chain
    /// </summary>
    public string Method { get; set; } = string.Empty;

    /// <summary>
    /// Source entity type: character, zone, item, quest, scripted
    /// </summary>
    public string SourceType { get; set; } = string.Empty;

    /// <summary>
    /// Reference to the source entity (nullable for scripted)
    /// </summary>
    public string? SourceStableKey { get; set; }

    /// <summary>
    /// Human-readable note (especially for scripted completions)
    /// </summary>
    public string? Note { get; set; }
}
