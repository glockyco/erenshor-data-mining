#nullable enable

using SQLite;

/// <summary>
/// Junction table for all quest acquisition sources.
/// Single source of truth for "how do I get this quest?"
///
/// Methods:
/// - dialog: NPC dialog assigns quest via NPCDialog.QuestToAssign
/// - item_read: Reading an item assigns quest via Item.AssignQuestOnRead
/// - zone_entry: Entering a zone assigns quest via ZoneAnnounce.AssignQuestOnEnter
/// - quest_chain: Completing another quest assigns this via Quest.AssignNewQuestOnComplete
/// - partial_turnin: Partial item turn-in assigns quest via Quest.AssignThisQuestOnPartialComplete
/// - scripted: Hardcoded in Unity scripts (ShiverEvent, etc.)
/// </summary>
[Table("QuestAcquisitionSources")]
public class QuestAcquisitionSourceRecord
{
    public const string TableName = "QuestAcquisitionSources";

    [Indexed(Name = "QuestAcquisitionSources_Quest_IDX")]
    [ForeignKey(typeof(QuestRecord), "StableKey")]
    public string QuestStableKey { get; set; } = string.Empty;

    /// <summary>
    /// Acquisition method: dialog, item_read, zone_entry, quest_chain, partial_turnin, scripted
    /// </summary>
    public string Method { get; set; } = string.Empty;

    /// <summary>
    /// Source entity type: character, item, zone, quest, scripted
    /// </summary>
    public string SourceType { get; set; } = string.Empty;

    /// <summary>
    /// Reference to the source entity (nullable for scripted)
    /// </summary>
    public string? SourceStableKey { get; set; }

    /// <summary>
    /// Human-readable note (especially for scripted acquisitions)
    /// </summary>
    public string? Note { get; set; }
}
